"""
compare_v2_on_off.py — Compara v2_enabled=true vs v2_enabled=false
==================================================================
Basado en el hallazgo del CFI audit (2026-04-14):
  corr(Sharpe, best_cMDA) = -0.381
  → Las 6 estrategias de mayor Sharpe no tienen señal en el meta-modelo.
  → H86 y H72 SÍ tienen señal.

Este script:
  1. Lee los resultados actuales (v2=true) de results/exploration/*.json
  2. Crea configs con v2_enabled=false para H136, H371, H434, H426, H236, H481
  3. Corre los backtests sin meta-modelo
  4. Imprime tabla comparativa Sharpe / Return / MaxDD / Trades / WinRate

H86 y H72 se mantienen con v2=true (meta-modelo aporta valor según CFI audit).

Uso:
  cd Patacon/
  python -m SopaDeOtoe.launchers.compare_v2_on_off [--n-jobs 4]
"""

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from typing import Optional
import yaml
import numpy as np
import pandas as pd

import SopaDeOtoe._path_setup  # noqa: F401
import SopaDeOtoe.strategies   # noqa: F401 — triggers BaseStrategy._REGISTRY

from SopaDeOtoe.core.runner import run_exploration

_SOPA_DIR       = Path(__file__).resolve().parent.parent
_GRADUATED_DIR  = _SOPA_DIR / "configs" / "graduated"
_MANIFEST_PATH  = _SOPA_DIR / "strategies" / "graduated_manifest.yaml"
_EXPLORATION_DIR = _SOPA_DIR / "results" / "exploration"
_V2OFF_DIR      = _SOPA_DIR / "results" / "v2_off"

# Estrategias donde v2 NO aporta según CFI audit → deshabilitar
V2_OFF_STRATEGIES = {
    "HypothesisH136GoldenDeathCrossAsym",
    "HypothesisH371MaxMinDualTriggerFreq",
    "HypothesisH434MaxMinDualHorizon",
    "HypothesisH426RSIGarchBullBear",
    "HypothesisH236MomentumReversalAsym",
    "HypothesisH481GoldenCrossPSAR",
}

# Estrategias donde v2 SÍ aporta → mantener tal cual
V2_ON_STRATEGIES = {
    "HypothesisH86WonhamMarkovRefinado",
    "HypothesisH72AsymmetricRSIDrawdownShield",
}

# Sharpe graduado (referencia del manifest original)
MANIFEST_SHARPE = {
    "HypothesisH136GoldenDeathCrossAsym":     0.9422,
    "HypothesisH371MaxMinDualTriggerFreq":     0.9332,
    "HypothesisH434MaxMinDualHorizon":         0.7228,
    "HypothesisH426RSIGarchBullBear":          0.6903,
    "HypothesisH236MomentumReversalAsym":      0.6337,
    "HypothesisH86WonhamMarkovRefinado":       0.6164,
    "HypothesisH481GoldenCrossPSAR":           0.6021,
    "HypothesisH72AsymmetricRSIDrawdownShield":0.4086,
}


def _load_graduated_configs():
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text())
    configs = []
    for entry in manifest["strategies"]:
        yaml_path = _SOPA_DIR / entry["config_file"]
        cfg = yaml.safe_load(yaml_path.read_text())
        cfg["_meta_strategy_class"] = entry["strategy_class"]
        cfg["_meta_run_id"]         = entry["run_id"]
        configs.append(cfg)
    return configs, manifest


def _read_existing_v2on_metrics(strategy_class: str) -> Optional[dict]:
    """
    Lee métricas del último run con v2=true desde results/exploration/.
    Busca el JSON con nombre que empiece por strategy_class.
    """
    for p in sorted(_EXPLORATION_DIR.glob(f"{strategy_class}_*.json"), reverse=True):
        try:
            data = json.loads(p.read_text())
            m = data.get("metrics", {})
            ts = data.get("trade_stats", {}) or {}
            if m:
                return {
                    "sharpe":         float(m.get("sharpe") or 0),
                    "total_return":   float(m.get("total_return") or m.get("cum_return") or 0),
                    "max_drawdown":   float(m.get("max_drawdown") or 0),
                    "calmar":         float(m.get("calmar") or 0),
                    "n_trades":       int(ts.get("total_trades") or ts.get("n_trades")
                                         or m.get("n_trades") or 0),
                    "win_rate":       float(ts.get("win_rate") or 0),
                    "profit_factor":  float(ts.get("profit_factor") or m.get("profit_factor") or 0),
                    "source":         str(p.name),
                }
        except Exception:
            continue
    return None


def _read_v12_run_metrics(v12_run_dir) -> Optional[dict]:
    """Lee métricas directamente del results.json del run v12."""
    try:
        results_path = Path(v12_run_dir) / "results.json"
        data = json.loads(results_path.read_text())
        m  = data.get("metrics", {}) or {}
        ts = data.get("trade_stats", {}) or {}
        return {
            "sharpe":        float(m.get("sharpe") or 0),
            "total_return":  float(m.get("total_return") or 0),
            "max_drawdown":  float(m.get("max_drawdown") or 0),
            "calmar":        float(m.get("calmar") or 0),
            "n_trades":      int(ts.get("total_trades") or ts.get("n_trades")
                                 or m.get("n_trades") or 0),
            "win_rate":      float(ts.get("win_rate") or 0),
            "profit_factor": float(ts.get("profit_factor") or m.get("profit_factor") or 0),
        }
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-jobs", type=int, default=3,
                    help="Parallel workers para run_exploration (default=3)")
    ap.add_argument("--skip-run", action="store_true",
                    help="Leer resultados v2=off ya existentes en results/v2_off/")
    args = ap.parse_args()

    configs, manifest = _load_graduated_configs()
    print(f"\n{'='*70}")
    print("  compare_v2_on_off — CFI Audit Follow-up (2026-04-14)")
    print(f"  {len(V2_OFF_STRATEGIES)} estrategias → v2_enabled=false")
    print(f"  {len(V2_ON_STRATEGIES)} estrategias → v2_enabled=true (H86, H72)")
    print(f"{'='*70}\n")

    # ── Leer v2=true metrics (de runs existentes) ─────────────────────────────
    print("[1/3] Leyendo métricas v2=true de results/exploration/ ...")
    v2on_metrics = {}
    for cfg in configs:
        cls = cfg["_meta_strategy_class"]
        m = _read_existing_v2on_metrics(cls)
        if m:
            v2on_metrics[cls] = m
            print(f"  OK   {cls:<50s} Sharpe={m['sharpe']:+.4f}")
        else:
            # Fall back to manifest reference Sharpe
            v2on_metrics[cls] = {
                "sharpe": MANIFEST_SHARPE.get(cls, 0.0),
                "total_return": 0, "max_drawdown": 0, "calmar": 0,
                "n_trades": 0, "win_rate": 0, "profit_factor": 0,
                "source": "manifest_fallback",
            }
            print(f"  WARN {cls:<50s} usando Sharpe del manifest={MANIFEST_SHARPE.get(cls,0):.4f}")

    # ── Construir configs v2=off ───────────────────────────────────────────────
    print(f"\n[2/3] Construyendo configs v2_enabled=false ...")
    v2off_configs = []
    for cfg in configs:
        cls = cfg["_meta_strategy_class"]
        if cls not in V2_OFF_STRATEGIES:
            continue  # H86 y H72 no corren aquí

        new_cfg = copy.deepcopy(cfg)
        # Desactivar el meta-modelo completamente
        new_cfg['v2']['v2_enabled'] = False
        # Config ID único para este experimento
        ts_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        short_name = cls.replace("Hypothesis", "")
        new_cfg["config_id"] = f"{short_name}_v2OFF_{ts_tag}"
        new_cfg["_meta_strategy_class"] = cls
        v2off_configs.append(new_cfg)
        print(f"  -> {new_cfg['config_id']}")

    # ── Correr o leer v2=off ───────────────────────────────────────────────────
    _V2OFF_DIR.mkdir(parents=True, exist_ok=True)

    if args.skip_run:
        print(f"\n[2/3] --skip-run: leyendo resultados previos de {_V2OFF_DIR} ...")
        v2off_results = []
        for cfg in v2off_configs:
            pattern = f"{cfg['_meta_strategy_class'].replace('Hypothesis','')}_v2OFF_*.json"
            matches = sorted(_V2OFF_DIR.glob(pattern), reverse=True)
            if matches:
                v2off_results.append(json.loads(matches[0].read_text()))
            else:
                print(f"  WARN no hay JSON para {cfg['config_id']}")
                v2off_results.append({"status": "error", "config_id": cfg["config_id"],
                                       "metrics": {}, "trade_stats": {}})
    else:
        print(f"\n[2/3] Corriendo {len(v2off_configs)} configs con v2_enabled=false "
              f"(n_jobs={args.n_jobs}) ...")
        print("      Esto tardará ~5-10 min por estrategia.\n")
        v2off_results = run_exploration(
            v2off_configs,
            n_jobs=args.n_jobs,
            output_dir=_V2OFF_DIR,
        )

    # ── Leer métricas v2=off de los run dirs ──────────────────────────────────
    v2off_metrics = {}
    for cfg, res in zip(v2off_configs, v2off_results):
        cls = cfg["_meta_strategy_class"]
        if res.get("status") == "success":
            run_dir = res.get("v12_run_dir")
            m = _read_v12_run_metrics(run_dir) if run_dir else None
            if m:
                v2off_metrics[cls] = m
            else:
                # Fallback: métricas directo del exploration JSON
                em = res.get("metrics", {})
                v2off_metrics[cls] = {
                    "sharpe":        float(em.get("sharpe") or 0),
                    "total_return":  float(em.get("cum_return") or em.get("total_return") or 0),
                    "max_drawdown":  float(em.get("max_drawdown") or 0),
                    "calmar":        float(em.get("calmar") or 0),
                    "n_trades":      int(em.get("n_trades") or 0),
                    "win_rate":      float(em.get("win_rate") or 0),
                    "profit_factor": float(em.get("profit_factor") or 0),
                }
        else:
            err = res.get("error", "?")[:80]
            print(f"  ERROR {cls}: {err}")
            v2off_metrics[cls] = None

    # ── Tabla comparativa ─────────────────────────────────────────────────────
    print(f"\n\n{'='*100}")
    print("  TABLA COMPARATIVA: v2=ON vs v2=OFF")
    print(f"  CFI audit finding: corr(Sharpe, cMDA) = -0.381")
    print(f"  Hipótesis: v2=OFF debería MEJORAR Sharpe en las 6 estrategias de señal pura.")
    print(f"{'='*100}\n")

    # Sort order: manifest Sharpe descendente
    order = sorted(MANIFEST_SHARPE.keys(), key=lambda k: -MANIFEST_SHARPE[k])

    hdr = (f"  {'Estrategia':<42} {'CFI':>5}  "
           f"{'Sharpe ON':>9} {'Sharpe OFF':>10} {'ΔSharpe':>8}  "
           f"{'nTrades ON':>10} {'nTrades OFF':>11}  "
           f"{'MaxDD ON':>8} {'MaxDD OFF':>9}  Veredicto")
    print(hdr)
    print("  " + "-" * 130)

    delta_rows = []
    for cls in order:
        on  = v2on_metrics.get(cls, {})
        off = v2off_metrics.get(cls)
        cfi_tag = "✓" if cls in V2_ON_STRATEGIES else "✗"

        s_on  = on.get("sharpe", 0.0)
        s_off = off.get("sharpe", 0.0) if off else float("nan")
        delta = s_off - s_on

        t_on  = on.get("n_trades", 0)
        t_off = off.get("n_trades", 0) if off else 0

        dd_on  = on.get("max_drawdown", 0.0)
        dd_off = off.get("max_drawdown", 0.0) if off else float("nan")

        if off is None:
            verdict = "ERROR en run"
        elif cls in V2_ON_STRATEGIES:
            verdict = "mantenido v2=ON (CFI señal)"
            s_off = float("nan")
            delta = float("nan")
        elif delta > 0.05:
            verdict = "MEJORA con v2=OFF ✓"
        elif delta > 0.01:
            verdict = "mejora leve"
        elif delta < -0.05:
            verdict = "v2 sí aportaba (sorpresa)"
        elif delta < -0.01:
            verdict = "pequeña regresión"
        else:
            verdict = "sin diferencia clara"

        s_off_str  = f"{s_off:+.4f}" if not (isinstance(s_off, float) and np.isnan(s_off)) else "  N/A  "
        delta_str  = f"{delta:+.4f}" if not (isinstance(delta, float) and np.isnan(delta)) else "  N/A "
        dd_off_str = f"{dd_off:.4f}" if not (isinstance(dd_off, float) and np.isnan(dd_off)) else "  N/A  "

        short = cls.replace("Hypothesis", "")
        print(f"  {short:<42} {cfi_tag:>5}  "
              f"{s_on:>9.4f} {s_off_str:>10} {delta_str:>8}  "
              f"{t_on:>10} {t_off:>11}  "
              f"{dd_on:>8.4f} {dd_off_str:>9}  {verdict}")

        delta_rows.append({"strategy": short, "delta_sharpe": delta,
                           "cfi_signal": cls in V2_ON_STRATEGIES})

    # Resumen cuantitativo
    valid_deltas = [r["delta_sharpe"] for r in delta_rows
                    if not r["cfi_signal"] and not np.isnan(r["delta_sharpe"])]
    if valid_deltas:
        print(f"\n  Δ Sharpe promedio (6 estrategias v2=OFF): {np.mean(valid_deltas):+.4f}")
        print(f"  Δ Sharpe mediana:                         {np.median(valid_deltas):+.4f}")
        n_improved = sum(1 for d in valid_deltas if d > 0.01)
        n_hurt     = sum(1 for d in valid_deltas if d < -0.01)
        print(f"  Mejoradas (Δ > 0.01): {n_improved}/6  |  Empeoradas (Δ < -0.01): {n_hurt}/6")

    print(f"\n  INTERPRETACIÓN:")
    if valid_deltas and np.mean(valid_deltas) > 0.05:
        print("  → v2=OFF MEJORA el Sharpe promedio.")
        print("    El meta-modelo estaba filtrando operaciones ganadoras (Type II error).")
        print("    La señal pura de cada estrategia es suficiente.")
    elif valid_deltas and np.mean(valid_deltas) > 0:
        print("  → v2=OFF mejora levemente. Meta-modelo aporta poco pero no daña.")
        print("    Considerar desactivarlo para reducir complejidad operacional.")
    elif valid_deltas and np.mean(valid_deltas) < -0.05:
        print("  → v2=ON es claramente mejor. El meta-modelo sí filtra ruido.")
        print("    El CFI audit puede haber sido afectado por alta correlación entre features.")
    else:
        print("  → Diferencias menores que el ruido estadístico.")
        print("    El meta-modelo ni ayuda ni perjudica significativamente.")

    print(f"\n{'='*100}")
    print("  H86 y H72 mantuvieron v2=ON (CFI audit: cMDA > noise floor)")
    print(f"{'='*100}\n")

    # Guardar JSON con resultados
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = _V2OFF_DIR / f"v2_comparison_{ts}.json"
    comparison_data = {
        "timestamp": ts,
        "finding": "CFI audit 2026-04-14: corr(Sharpe, best_cMDA) = -0.381",
        "v2_off_strategies": sorted(V2_OFF_STRATEGIES),
        "v2_on_strategies": sorted(V2_ON_STRATEGIES),
        "results": [
            {
                "strategy": cls.replace("Hypothesis", ""),
                "cfi_signal": cls in V2_ON_STRATEGIES,
                "v2_on": v2on_metrics.get(cls, {}),
                "v2_off": v2off_metrics.get(cls) or {},
                "delta_sharpe": (
                    (v2off_metrics[cls]["sharpe"] - v2on_metrics.get(cls, {}).get("sharpe", 0))
                    if v2off_metrics.get(cls) and cls not in V2_ON_STRATEGIES
                    else None
                ),
            }
            for cls in order
        ],
    }
    out_path.write_text(json.dumps(comparison_data, indent=2, default=str))
    print(f"  Resultados guardados: {out_path}\n")


if __name__ == "__main__":
    main()
