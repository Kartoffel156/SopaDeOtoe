"""
run_cpcv_validation.py — CPCV de 15 paths para las 6 estrategias donde v2 añade valor
========================================================================================
Basado en hallazgo compare_v2_on_off (2026-04-14):
  → v2=ON mejora Sharpe drásticamente vs v2=OFF en H136/H371/H434/H426/H236/H481
  → Las runs existentes solo tienen C(4,2)=6 paths (sub-mínimo AFML Cap.12)

Este script re-corre las 6 estrategias con:
  cpcv_n_splits: 6, cpcv_n_test_groups: 2 → C(6,2) = 15 paths
  validation_method: cpcv, cpcv_mode: genuine

Produce tabla: p5 / p25 / p50 / p75 / p95 / %positive / DSR
Compara contra v2=OFF Sharpe (referencia del compare_v2_on_off.py)

Uso:
  cd Patacon/
  python -m SopaDeOtoe.launchers.run_cpcv_validation [--n-jobs 3]
"""

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
import numpy as np

import SopaDeOtoe._path_setup   # noqa: F401
import SopaDeOtoe.strategies    # noqa: F401

from SopaDeOtoe.core.runner import run_exploration

_SOPA_DIR     = Path(__file__).resolve().parent.parent
_GRADUATED_DIR = _SOPA_DIR / "configs" / "graduated"
_MANIFEST_PATH = _SOPA_DIR / "strategies" / "graduated_manifest.yaml"
_CPCV_DIR     = _SOPA_DIR / "results" / "cpcv_validation"
_V2OFF_DIR    = _SOPA_DIR / "results" / "v2_off"

# Las 6 donde v2 añade valor (según compare_v2_on_off)
PRIORITY_STRATEGIES = [
    "HypothesisH136GoldenDeathCrossAsym",
    "HypothesisH371MaxMinDualTriggerFreq",
    "HypothesisH434MaxMinDualHorizon",
    "HypothesisH426RSIGarchBullBear",
    "HypothesisH236MomentumReversalAsym",
    "HypothesisH481GoldenCrossPSAR",
]

# v2=OFF Sharpe de referencia (del último compare_v2_on_off)
V2OFF_SHARPE = {
    "HypothesisH136GoldenDeathCrossAsym":   -1.3768,
    "HypothesisH371MaxMinDualTriggerFreq":  -1.4706,
    "HypothesisH434MaxMinDualHorizon":      -0.2619,
    "HypothesisH426RSIGarchBullBear":       -1.3405,
    "HypothesisH236MomentumReversalAsym":   -0.6428,
    "HypothesisH481GoldenCrossPSAR":        -0.5208,
}

MANIFEST_SHARPE = {
    "HypothesisH136GoldenDeathCrossAsym":   0.9422,
    "HypothesisH371MaxMinDualTriggerFreq":  0.9332,
    "HypothesisH434MaxMinDualHorizon":      0.7228,
    "HypothesisH426RSIGarchBullBear":       0.6903,
    "HypothesisH236MomentumReversalAsym":   0.6337,
    "HypothesisH481GoldenCrossPSAR":        0.6021,
}


def _load_graduated_configs():
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text())
    out = {}
    for entry in manifest["strategies"]:
        cls = entry["strategy_class"]
        if cls not in PRIORITY_STRATEGIES:
            continue
        yaml_path = _SOPA_DIR / entry["config_file"]
        cfg = yaml.safe_load(yaml_path.read_text())
        out[cls] = cfg
    return out


def _build_cpcv_config(cls: str, base_cfg: dict) -> dict:
    """Crea config con CPCV 15-paths (C(6,2)) y montecarlo reducido."""
    cfg = copy.deepcopy(base_cfg)
    ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # CPCV 15 paths
    cfg["v2"]["cpcv_n_splits"]      = 6
    cfg["v2"]["cpcv_n_test_groups"] = 2
    cfg["v2"]["cpcv_mode"]          = "genuine"
    cfg["validation_method"]        = "cpcv"

    # Reducir MC para acelerar (el objetivo es CPCV, no MC)
    cfg["montecarlo"]["reshuffling"]["enabled"]   = False
    cfg["montecarlo"]["reality_check"]["enabled"] = False
    cfg["montecarlo"]["stress"]["enabled"]        = False
    cfg["montecarlo"]["bootstrap"]["enabled"]     = False

    cfg["config_id"] = f"{cls.replace('Hypothesis','')}_CPCV15_{ts}"
    cfg["_meta_strategy_class"] = cls
    return cfg


def _extract_cpcv(v12_run_dir: str) -> dict:
    """Lee la distribución CPCV del results.json."""
    data = json.loads((Path(v12_run_dir) / "results.json").read_text())
    cpcv = data.get("cpcv_distribution", {})
    metrics = data.get("metrics", {})

    dist_raw = cpcv.get("sharpe_distribution", "")
    vals = []
    for line in dist_raw.split("\n"):
        parts = line.strip().split()
        if parts:
            try:
                vals.append(float(parts[-1]))
            except ValueError:
                pass

    pct = cpcv.get("percentiles", {})
    return {
        "full_sharpe":    float(metrics.get("sharpe") or 0),
        "n_paths":        len(vals),
        "paths":          vals,
        "p5":             float(pct.get("5", 0)),
        "p25":            float(pct.get("25", 0)),
        "p50":            float(pct.get("50", 0)),
        "p75":            float(pct.get("75", 0)),
        "p95":            float(pct.get("95", 0)),
        "mean":           float(cpcv.get("mean", 0)),
        "std":            float(cpcv.get("std", 1)),
        "n_positive":     sum(1 for v in vals if v > 0),
        "max_drawdown":   float(metrics.get("max_drawdown") or 0),
        "n_trades":       int(
            (data.get("trade_stats") or {}).get("total_trades")
            or metrics.get("n_trades") or 0
        ),
    }


def _dsr(sharpe_obs: float, n_paths: int, t: int, skew: float = 0.0, kurt: float = 3.0) -> float:
    """
    Deflated Sharpe Ratio (AFML Snippet 8.2 / Bailey & López de Prado 2014).
    Adjusts SR for multiple testing over n_paths CPCV paths.
    t = number of observations used to compute SR.
    """
    from scipy.stats import norm
    import math

    if n_paths < 2 or t < 2:
        return float("nan")

    # Expected maximum SR from n_paths IID trials (Bailey & López de Prado eq 4)
    gamma_euler = 0.5772156649
    e_max_sr = (
        (1 - gamma_euler) * norm.ppf(1 - 1.0 / n_paths)
        + gamma_euler * norm.ppf(1 - 1.0 / (n_paths * np.e))
    )

    # SR std (annualized is SR/sqrt(t) * sqrt(1 + ...))
    sr_std = math.sqrt(
        (1 - skew * sharpe_obs + (kurt - 1) / 4.0 * sharpe_obs ** 2) / (t - 1)
    )
    if sr_std < 1e-12:
        return float("nan")

    z = (sharpe_obs - e_max_sr) / sr_std
    return float(norm.cdf(z))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-jobs", type=int, default=3)
    ap.add_argument("--skip-run", action="store_true",
                    help="Leer resultados ya existentes en results/cpcv_validation/")
    args = ap.parse_args()

    print(f"\n{'='*72}")
    print("  CPCV Validation — 6 Estrategias con v2=ON  (C(6,2)=15 paths)")
    print("  AFML Cap. 12 mínimo: 15 paths para distribución estadísticamente válida")
    print(f"{'='*72}\n")

    base_configs = _load_graduated_configs()
    cpcv_configs = [_build_cpcv_config(cls, cfg)
                    for cls, cfg in base_configs.items()]

    _CPCV_DIR.mkdir(parents=True, exist_ok=True)

    # ── Correr o leer ──────────────────────────────────────────────────────────
    if args.skip_run:
        print("[1/2] --skip-run: leyendo resultados previos ...")
        results = []
        for cfg in cpcv_configs:
            cls = cfg["_meta_strategy_class"]
            short = cls.replace("Hypothesis", "")
            pattern = f"{short}_CPCV15_*.json"
            matches = sorted(_CPCV_DIR.glob(pattern), reverse=True)
            if matches:
                results.append(json.loads(matches[0].read_text()))
            else:
                print(f"  WARN: sin resultados para {short}")
                results.append({"status": "error", "config_id": cfg["config_id"],
                                 "metrics": {}, "trade_stats": {}})
    else:
        print(f"[1/2] Corriendo {len(cpcv_configs)} strategies con CPCV 15-paths "
              f"(n_jobs={args.n_jobs}) ...")
        print("      ~10-20 min por estrategia (OOS completo + 15 CPCV paths)\n")
        results = run_exploration(
            cpcv_configs,
            n_jobs=args.n_jobs,
            output_dir=_CPCV_DIR,
        )

    # ── Extraer y mostrar ──────────────────────────────────────────────────────
    print(f"\n[2/2] Analizando distribuciones CPCV ...\n")

    all_data = {}
    for cfg, res in zip(cpcv_configs, results):
        cls = cfg["_meta_strategy_class"]
        short = cls.replace("Hypothesis", "")[:38]

        if res.get("status") != "success":
            err = res.get("error", "?")[:80]
            print(f"  ERROR {short}: {err}")
            all_data[cls] = None
            continue

        v12_dir = res.get("v12_run_dir")
        if not v12_dir:
            print(f"  ERROR {short}: no v12_run_dir")
            all_data[cls] = None
            continue

        try:
            c = _extract_cpcv(v12_dir)
        except Exception as e:
            print(f"  ERROR {short} leyendo CPCV: {e}")
            all_data[cls] = None
            continue

        all_data[cls] = c

        # DSR: use n_trades as proxy for t (number of independent observations)
        dsr_val = _dsr(
            sharpe_obs=c["full_sharpe"],
            n_paths=c["n_paths"],
            t=max(c["n_trades"], 30),
        )

        print(f"  {short}")
        print(f"    Full Sharpe : {c['full_sharpe']:+.4f}   MaxDD: {c['max_drawdown']:.4f}   Trades: {c['n_trades']}")
        print(f"    CPCV paths  : {c['n_paths']}  ({c['n_positive']}/{c['n_paths']} positivos)")
        print(f"    Distribution: p5={c['p5']:+.2f}  p25={c['p25']:+.2f}  p50={c['p50']:+.2f}  "
              f"p75={c['p75']:+.2f}  p95={c['p95']:+.2f}")
        print(f"    mean={c['mean']:+.2f}  std={c['std']:.2f}  "
              f"DSR={f'{dsr_val:.4f}' if not (isinstance(dsr_val,float) and dsr_val!=dsr_val) else 'N/A'}")
        v2off = V2OFF_SHARPE.get(cls, float("nan"))
        pct_above_v2off = sum(1 for v in c["paths"] if v > v2off) / len(c["paths"]) * 100 if c["paths"] else 0
        print(f"    v2=OFF ref  : {v2off:+.4f}   CPCV paths > v2=OFF: {pct_above_v2off:.0f}%")
        print()

    # ── Tabla resumen ──────────────────────────────────────────────────────────
    print(f"\n{'='*100}")
    print("  RESUMEN CPCV — 15 paths (C(6,2)) vs v2=OFF Sharpe")
    print(f"{'='*100}")
    print(f"\n  {'Estrategia':<40} {'Sharpe':>7} {'p5':>7} {'p50':>7} {'p95':>7} "
          f"{'%pos':>5} {'DSR':>6}  {'v2=OFF':>7}  Robustez")
    print("  " + "-" * 105)

    for cls in PRIORITY_STRATEGIES:
        c = all_data.get(cls)
        short = cls.replace("Hypothesis", "")[:40]
        v2off = V2OFF_SHARPE.get(cls, float("nan"))

        if c is None:
            print(f"  {short:<40} ERROR")
            continue

        pos_pct = c["n_positive"] / c["n_paths"] * 100 if c["n_paths"] > 0 else 0
        dsr_val = _dsr(c["full_sharpe"], c["n_paths"], max(c["n_trades"], 30))
        dsr_str = f"{dsr_val:.3f}" if not (isinstance(dsr_val,float) and dsr_val!=dsr_val) else " N/A"

        if pos_pct == 100 and c["p5"] > 0:
            robustez = "FUERTE (todos positivos, p5>0)"
        elif pos_pct >= 80 and c["p5"] > v2off:
            robustez = "ROBUSTO (p5 > v2=OFF)"
        elif pos_pct >= 60:
            robustez = "MODERADO"
        else:
            robustez = "DÉBIL"

        print(f"  {short:<40} {c['full_sharpe']:>7.4f} {c['p5']:>7.2f} {c['p50']:>7.2f} "
              f"{c['p95']:>7.2f} {pos_pct:>5.0f}% {dsr_str:>6}  "
              f"{v2off:>7.4f}  {robustez}")

    # ── Interpretación ────────────────────────────────────────────────────────
    valid = [c for c in all_data.values() if c]
    if valid:
        all_pos = [c["n_positive"] / c["n_paths"] for c in valid if c["n_paths"] > 0]
        all_p5  = [c["p5"] for c in valid]
        print(f"\n  Promedio %paths positivos : {np.mean(all_pos)*100:.1f}%")
        print(f"  Promedio p5               : {np.mean(all_p5):+.2f}")
        print(f"\n  INTERPRETACIÓN:")
        if np.mean(all_pos) >= 0.8:
            print("  → Robustez confirmada. El Sharpe de las 6 estrategias es estadísticamente")
            print("    sólido: la mayoría de los 15 CPCV paths muestra Sharpe positivo.")
            print("    El meta-modelo (v2=ON) añade valor real fuera de muestra.")
        elif np.mean(all_pos) >= 0.6:
            print("  → Robustez moderada. Hay paths negativos que merecen análisis adicional.")
            print("    Revisar si los paths negativos coinciden con regímenes bear.")
        else:
            print("  → Robustez débil. El edge puede ser fragil o concentrado en pocos períodos.")

    # ── Guardar ───────────────────────────────────────────────────────────────
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = {
        "timestamp": ts,
        "cpcv_config": "C(6,2)=15 paths, genuine mode",
        "v2off_reference": V2OFF_SHARPE,
        "results": {
            cls.replace("Hypothesis", ""): {
                "full_sharpe":  MANIFEST_SHARPE.get(cls),
                "cpcv":         all_data.get(cls),
                "v2off_sharpe": V2OFF_SHARPE.get(cls),
            }
            for cls in PRIORITY_STRATEGIES
        },
    }
    out_path = _CPCV_DIR / f"cpcv_validation_{ts}.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n  Guardado: {out_path}\n")
    print(f"{'='*100}\n")


if __name__ == "__main__":
    main()
