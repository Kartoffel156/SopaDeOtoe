"""
compare_allocation_methods.py — Comparación lado a lado de los 5 métodos
de asignación de pesos sobre la misma cohorte de estrategias graduadas.

Métodos:
  1. equal_weight   — 1/N naive (benchmark DeMiguel et al. 2009)
  2. inverse_vol    — Carver default / Roncalli ρ=0
  3. erc            — Equal Risk Contribution (Roncalli Cap. 2)
  4. hrp            — Hierarchical Risk Parity (Prado AFML Cap. 16)
  5. risk_budget    — Generalized RB con budgets = 1/N (≈ ERC, distinto solver path)

Uso:
    cd Patacon/
    python -m SopaDeOtoe.launchers.compare_allocation_methods [--output-dir results/portfolio]
"""

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import SopaDeOtoe._path_setup  # noqa: F401
import SopaDeOtoe.strategies   # noqa: F401

from portfolio.data_structures import StrategyResult
from portfolio.portfolio_config import load_portfolio_config
from portfolio.runner import run_portfolio_backtest
from SopaDeOtoe.launchers.run_graduated_backtest import (
    _load_graduated_configs,
    _results_to_strategy_result,
)

_SOPA_DIR = Path(__file__).resolve().parent.parent
_EXPLORATION_DIR = _SOPA_DIR / "results" / "exploration"
_PORTFOLIO_CFG_PATH = _SOPA_DIR / "config" / "portfolio_settings.yaml"
_PORTFOLIO_OUT_DIR = _SOPA_DIR / "results" / "portfolio"

METHODS = ["equal_weight", "inverse_vol", "erc", "hrp", "risk_budget"]


def _load_strategy_results() -> list[StrategyResult]:
    """Load pre-computed strategy results from exploration dir."""
    configs, manifest = _load_graduated_configs()
    results = []
    for cfg in configs:
        cid = cfg["config_id"]
        path = _EXPLORATION_DIR / f"{cid}.json"
        if not path.exists():
            print(f"  SKIP {cid}: no existe {path}")
            continue
        res = json.loads(path.read_text())
        if res.get("status") != "success":
            continue
        run_dir = Path(res["v12_run_dir"])
        cls = cfg["_meta_strategy_class"]
        try:
            sr = _results_to_strategy_result(cls, run_dir, n_trials=cfg.get("n_trials", 1))
            results.append(sr)
        except Exception as e:
            print(f"  SKIP {cls}: {e}")
    return results


def _base_config():
    """Load portfolio config with fast overrides (no MC for speed)."""
    cfg = load_portfolio_config(_PORTFOLIO_CFG_PATH)
    cfg.risk.target_volatility = 0.10
    cfg.validation.n_permutations = 1000
    cfg.validation.n_bootstrap = 1000
    cfg.validation.run_stress_test = False
    cfg.validation.run_spa_test = False
    cfg.validation.run_cpcv = True
    cfg.validation.cpcv_n_groups = 6
    cfg.validation.cpcv_n_test_groups = 2
    cfg.validation.cpcv_embargo_pct = 0.01
    return cfg


def _load_strategy_level_validation() -> dict:
    """Load CPCV and MC reshuffling from individual v12 results."""
    configs, _ = _load_graduated_configs()
    strat_validation = {}
    for cfg in configs:
        cid = cfg["config_id"]
        path = _EXPLORATION_DIR / f"{cid}.json"
        if not path.exists():
            continue
        res = json.loads(path.read_text())
        if res.get("status") != "success":
            continue
        run_dir = Path(res["v12_run_dir"])
        try:
            data = json.loads((run_dir / "results.json").read_text())
        except Exception:
            continue
        cls = cfg["_meta_strategy_class"]
        cpcv = data.get("cpcv_distribution", {})
        mc_resh = data.get("montecarlo", {}).get("reshuffling", {})
        strat_validation[cls] = {
            "cpcv_mean": float(cpcv.get("mean", 0)) if isinstance(cpcv, dict) else 0,
            "cpcv_std": float(cpcv.get("std", 0)) if isinstance(cpcv, dict) else 0,
            "cpcv_percentiles": cpcv.get("percentiles", {}) if isinstance(cpcv, dict) else {},
            "cpcv_sharpe_dist": cpcv.get("sharpe_distribution", None),
            "mc_p_sharpe": float(mc_resh.get("p_value_sharpe", 0)),
            "mc_p_maxdd": float(mc_resh.get("p_value_maxdd", 0)),
            "mc_p_return": float(mc_resh.get("p_value_return", 0)),
            "mc_ci_sharpe": mc_resh.get("ci_sharpe", {}),
            "mc_ci_maxdd": mc_resh.get("ci_maxdd", {}),
            "mc_ci_return": mc_resh.get("ci_return", {}),
            "mc_fragility": mc_resh.get("fragility", {}),
        }
    return strat_validation


def _run_single_method(method: str, strategy_results: list[StrategyResult]) -> dict:
    """Run portfolio backtest with a specific allocation method."""
    cfg = _base_config()
    cfg.allocation.method = method
    pr = run_portfolio_backtest(strategy_results, cfg)

    # Extract MC results
    mc = pr.montecarlo
    mc_summary = {}
    if "permutation" in mc:
        p = mc["permutation"]
        mc_summary["perm_observed_sharpe"] = float(p.get("observed_sharpe", 0))
        mc_summary["perm_p_value"] = float(p.get("p_value", 0))
        mc_summary["perm_mean_sharpe"] = float(p.get("mean_perm_sharpe", 0))
        mc_summary["perm_std_sharpe"] = float(p.get("std_perm_sharpe", 0))
    if "bootstrap" in mc:
        b = mc["bootstrap"]
        mc_summary["boot_sharpe_mean"] = float(b.get("sharpe_mean", 0))
        mc_summary["boot_sharpe_std"] = float(b.get("sharpe_std", 0))
        ci = b.get("sharpe_ci_95", (0, 0))
        mc_summary["boot_sharpe_ci_lo"] = float(ci[0])
        mc_summary["boot_sharpe_ci_hi"] = float(ci[1])
        mc_summary["boot_prob_neg_sharpe"] = float(b.get("prob_negative_sharpe", 0))
        dd_ci = b.get("max_dd_ci_95", (0, 0))
        mc_summary["boot_maxdd_ci_lo"] = float(dd_ci[0])
        mc_summary["boot_maxdd_ci_hi"] = float(dd_ci[1])
    if "cpcv" in mc:
        c = mc["cpcv"]
        mc_summary["cpcv_mean"] = float(c.get("mean", 0))
        mc_summary["cpcv_std"] = float(c.get("std", 0))
        mc_summary["cpcv_prob_neg"] = float(c.get("prob_negative_sharpe", 1))
        mc_summary["cpcv_n_paths"] = int(c.get("n_paths", 0))
        mc_summary["cpcv_n_valid"] = int(c.get("n_valid_paths", 0))
        mc_summary["cpcv_fdm_mean"] = float(c.get("fdm_mean", 0))
        mc_summary["cpcv_fdm_std"] = float(c.get("fdm_std", 0))
        pcts = c.get("percentiles", {})
        mc_summary["cpcv_p5"] = float(pcts.get("5", 0))
        mc_summary["cpcv_p25"] = float(pcts.get("25", 0))
        mc_summary["cpcv_p50"] = float(pcts.get("50", 0))
        mc_summary["cpcv_p75"] = float(pcts.get("75", 0))
        mc_summary["cpcv_p95"] = float(pcts.get("95", 0))
        mc_summary["cpcv_weight_stability"] = c.get("weight_stability", {})
        # Return and MaxDD distributions
        ret_dist = c.get("return_distribution", np.array([]))
        dd_dist = c.get("max_dd_distribution", np.array([]))
        if len(ret_dist) > 0:
            mc_summary["cpcv_return_mean"] = float(ret_dist.mean())
            mc_summary["cpcv_return_p5"] = float(np.percentile(ret_dist, 5))
            mc_summary["cpcv_return_p50"] = float(np.percentile(ret_dist, 50))
        if len(dd_dist) > 0:
            mc_summary["cpcv_maxdd_mean"] = float(dd_dist.mean())
            mc_summary["cpcv_maxdd_p5"] = float(np.percentile(dd_dist, 5))

    return {
        "method": method,
        "weights": {n: float(w) for n, w in zip(pr.strategy_names, pr.weights)},
        "fdm": float(pr.fdm),
        "metrics": {
            k: v for k, v in pr.metrics.items()
            if k != "risk_attribution" and isinstance(v, (int, float))
        },
        "risk_attribution": (
            pr.metrics["risk_attribution"].to_dict(orient="records")
            if "risk_attribution" in pr.metrics else None
        ),
        "combined_returns": pr.combined_returns,
        "combined_equity": pr.combined_equity,
        "montecarlo": mc_summary,
    }


def _print_comparison(results: list[dict], strategy_results: list[StrategyResult]):
    """Print side-by-side comparison table."""

    print("\n" + "=" * 100)
    print("  COMPARACIÓN DE MÉTODOS DE ASIGNACIÓN — first cohort")
    print("=" * 100)

    # --- Weights table ---
    names = list(results[0]["weights"].keys())
    short_names = [n.replace("Hypothesis", "").replace("Asym", "")[:20] for n in names]

    print("\n  PESOS POR MÉTODO:")
    header = f"  {'Estrategia':<22s}" + "".join(f"  {r['method']:>14s}" for r in results)
    print(header)
    print("  " + "-" * (22 + 16 * len(results)))
    for name, short in zip(names, short_names):
        row = f"  {short:<22s}"
        for r in results:
            row += f"  {r['weights'][name]:14.4f}"
        print(row)

    # FDM row
    row_fdm = f"  {'FDM':<22s}"
    for r in results:
        row_fdm += f"  {r['fdm']:14.4f}"
    print(row_fdm)

    # --- Metrics table ---
    metric_keys = [
        "sharpe", "annualized_return", "annualized_volatility",
        "max_drawdown", "calmar", "sortino", "diversification_ratio",
        "portfolio_volatility", "exposure",
    ]
    metric_labels = {
        "sharpe": "Sharpe",
        "annualized_return": "Ann. Return",
        "annualized_volatility": "Ann. Vol",
        "max_drawdown": "Max DD",
        "calmar": "Calmar",
        "sortino": "Sortino",
        "diversification_ratio": "Div. Ratio",
        "portfolio_volatility": "Port. Vol",
        "exposure": "Exposure",
    }

    print(f"\n  MÉTRICAS DE PORTFOLIO:")
    header = f"  {'Métrica':<22s}" + "".join(f"  {r['method']:>14s}" for r in results)
    print(header)
    print("  " + "-" * (22 + 16 * len(results)))
    for mk in metric_keys:
        label = metric_labels.get(mk, mk)
        row = f"  {label:<22s}"
        for r in results:
            val = r["metrics"].get(mk, float("nan"))
            row += f"  {val:+14.4f}"
        print(row)

    # --- Risk contribution concentration (Herfindahl) ---
    print(f"\n  CONCENTRACIÓN DE RIESGO (Herfindahl de RC%):")
    header = f"  {'Métrica':<22s}" + "".join(f"  {r['method']:>14s}" for r in results)
    print(header)
    print("  " + "-" * (22 + 16 * len(results)))
    for r in results:
        ra = r.get("risk_attribution")
        if ra:
            rc_pcts = [x["risk_contribution_pct"] for x in ra]
            r["_herfindahl"] = sum(p**2 for p in rc_pcts)
            r["_max_rc"] = max(rc_pcts)
            r["_min_rc"] = min(rc_pcts)
        else:
            r["_herfindahl"] = float("nan")
            r["_max_rc"] = float("nan")
            r["_min_rc"] = float("nan")

    row_h = f"  {'Herfindahl':<22s}"
    row_max = f"  {'Max RC%':<22s}"
    row_min = f"  {'Min RC%':<22s}"
    for r in results:
        row_h += f"  {r['_herfindahl']:14.4f}"
        row_max += f"  {r['_max_rc']:14.4f}"
        row_min += f"  {r['_min_rc']:14.4f}"
    print(row_h)
    print(row_max)
    print(row_min)

    # --- Equity curve stats ---
    print(f"\n  EQUITY CURVE (final):")
    header = f"  {'Métrica':<22s}" + "".join(f"  {r['method']:>14s}" for r in results)
    print(header)
    print("  " + "-" * (22 + 16 * len(results)))
    row_final = f"  {'Final Equity':<22s}"
    row_peak = f"  {'Peak Equity':<22s}"
    for r in results:
        eq = r["combined_equity"]
        row_final += f"  {float(eq.iloc[-1]):14.4f}"
        row_peak += f"  {float(eq.max()):14.4f}"
    print(row_final)
    print(row_peak)

    # --- Risk attribution detail per method ---
    print(f"\n  RISK ATTRIBUTION DETALLADA (RC% por estrategia):")
    header = f"  {'Estrategia':<22s}" + "".join(f"  {r['method']:>14s}" for r in results)
    print(header)
    print("  " + "-" * (22 + 16 * len(results)))
    for i, (name, short) in enumerate(zip(names, short_names)):
        row = f"  {short:<22s}"
        for r in results:
            ra = r.get("risk_attribution")
            if ra and i < len(ra):
                row += f"  {ra[i]['risk_contribution_pct']:14.4f}"
            else:
                row += f"  {'n/a':>14s}"
        print(row)

    # --- Best method per metric ---
    print(f"\n  RANKING (mejor método por métrica):")
    for mk in metric_keys:
        vals = [(r["method"], r["metrics"].get(mk, float("-inf"))) for r in results]
        if mk == "max_drawdown":
            best = max(vals, key=lambda x: x[1])
        elif mk in ("annualized_volatility", "portfolio_volatility"):
            continue
        else:
            best = max(vals, key=lambda x: x[1])
        label = metric_labels.get(mk, mk)
        print(f"    {label:<22s} -> {best[0]} ({best[1]:+.4f})")

    # --- Monte Carlo: Portfolio-level ---
    print(f"\n{'=' * 100}")
    print("  MONTE CARLO — PORTFOLIO LEVEL")
    print("=" * 100)

    mc_keys_perm = [
        ("perm_observed_sharpe", "Perm Obs Sharpe"),
        ("perm_p_value", "Perm p-value"),
        ("perm_mean_sharpe", "Perm Mean Sharpe"),
        ("perm_std_sharpe", "Perm Std Sharpe"),
    ]
    mc_keys_boot = [
        ("boot_sharpe_mean", "Boot Sharpe Mean"),
        ("boot_sharpe_std", "Boot Sharpe Std"),
        ("boot_sharpe_ci_lo", "Boot Sharpe 2.5%"),
        ("boot_sharpe_ci_hi", "Boot Sharpe 97.5%"),
        ("boot_prob_neg_sharpe", "P(Sharpe < 0)"),
        ("boot_maxdd_ci_lo", "Boot MaxDD 2.5%"),
        ("boot_maxdd_ci_hi", "Boot MaxDD 97.5%"),
    ]

    print(f"\n  PERMUTATION TEST (H0: asignación strategy->weight no importa):")
    header = f"  {'Métrica':<22s}" + "".join(f"  {r['method']:>14s}" for r in results)
    print(header)
    print("  " + "-" * (22 + 16 * len(results)))
    for mk, label in mc_keys_perm:
        row = f"  {label:<22s}"
        for r in results:
            val = r["montecarlo"].get(mk, float("nan"))
            row += f"  {val:14.4f}"
        print(row)

    # Interpretation
    print("\n  Interpretación permutation:")
    for r in results:
        pv = r["montecarlo"].get("perm_p_value", 1.0)
        sig = "***" if pv < 0.01 else "**" if pv < 0.05 else "*" if pv < 0.10 else "ns"
        print(f"    {r['method']:>14s}: p={pv:.3f} {sig}  — {'la asignación captura estructura real' if pv < 0.05 else 'no significativo'}")

    print(f"\n  BLOCK BOOTSTRAP (Politis-Romano, block=21, n=1000):")
    header = f"  {'Métrica':<22s}" + "".join(f"  {r['method']:>14s}" for r in results)
    print(header)
    print("  " + "-" * (22 + 16 * len(results)))
    for mk, label in mc_keys_boot:
        row = f"  {label:<22s}"
        for r in results:
            val = r["montecarlo"].get(mk, float("nan"))
            row += f"  {val:14.4f}"
        print(row)

    # Bootstrap CI interpretation
    print("\n  Interpretación bootstrap:")
    for r in results:
        lo = r["montecarlo"].get("boot_sharpe_ci_lo", 0)
        hi = r["montecarlo"].get("boot_sharpe_ci_hi", 0)
        pneg = r["montecarlo"].get("boot_prob_neg_sharpe", 0)
        dd_lo = r["montecarlo"].get("boot_maxdd_ci_lo", 0)
        dd_hi = r["montecarlo"].get("boot_maxdd_ci_hi", 0)
        print(f"    {r['method']:>14s}: Sharpe CI95=[{lo:+.3f}, {hi:+.3f}]  P(neg)={pneg:.1%}  MaxDD CI95=[{dd_lo:.3f}, {dd_hi:.3f}]")

    # --- CPCV Portfolio-Level ---
    has_cpcv = any("cpcv_mean" in r["montecarlo"] for r in results)
    if has_cpcv:
        print(f"\n{'=' * 100}")
        print("  CPCV PORTFOLIO-LEVEL (Prado AFML Cap. 12, adaptado al combinator)")
        print("  Train: estima covarianza → pesos → FDM.  Test: combina retornos OOS.")
        print("=" * 100)

        cpcv_keys = [
            ("cpcv_mean", "OOS Sharpe Mean"),
            ("cpcv_std", "OOS Sharpe Std"),
            ("cpcv_p5", "OOS Sharpe p5"),
            ("cpcv_p25", "OOS Sharpe p25"),
            ("cpcv_p50", "OOS Sharpe p50"),
            ("cpcv_p75", "OOS Sharpe p75"),
            ("cpcv_p95", "OOS Sharpe p95"),
            ("cpcv_prob_neg", "P(Sharpe < 0)"),
            ("cpcv_n_paths", "N paths"),
            ("cpcv_n_valid", "N valid paths"),
            ("cpcv_fdm_mean", "FDM mean"),
            ("cpcv_fdm_std", "FDM std"),
        ]

        print(f"\n  SHARPE OOS POR MÉTODO:")
        header = f"  {'Métrica':<22s}" + "".join(f"  {r['method']:>14s}" for r in results)
        print(header)
        print("  " + "-" * (22 + 16 * len(results)))
        for mk, label in cpcv_keys:
            row = f"  {label:<22s}"
            for r in results:
                val = r["montecarlo"].get(mk, float("nan"))
                if mk in ("cpcv_n_paths", "cpcv_n_valid"):
                    row += f"  {int(val):14d}"
                else:
                    row += f"  {val:14.4f}"
            print(row)

        # Return and MaxDD OOS
        cpcv_extra = [
            ("cpcv_return_mean", "OOS Return Mean"),
            ("cpcv_return_p5", "OOS Return p5"),
            ("cpcv_return_p50", "OOS Return p50"),
            ("cpcv_maxdd_mean", "OOS MaxDD Mean"),
            ("cpcv_maxdd_p5", "OOS MaxDD p5"),
        ]
        print(f"\n  RETURN Y MAXDD OOS:")
        header = f"  {'Métrica':<22s}" + "".join(f"  {r['method']:>14s}" for r in results)
        print(header)
        print("  " + "-" * (22 + 16 * len(results)))
        for mk, label in cpcv_extra:
            row = f"  {label:<22s}"
            for r in results:
                val = r["montecarlo"].get(mk, float("nan"))
                row += f"  {val:14.4f}"
            print(row)

        # Weight stability
        print(f"\n  ESTABILIDAD DE PESOS (std across CPCV paths):")
        names_w = list(results[0]["weights"].keys())
        short_w = [n.replace("Hypothesis", "").replace("Asym", "")[:20] for n in names_w]
        header = f"  {'Estrategia':<22s}" + "".join(f"  {r['method']:>14s}" for r in results)
        print(header)
        print("  " + "-" * (22 + 16 * len(results)))
        for name, short in zip(names_w, short_w):
            row = f"  {short:<22s}"
            for r in results:
                ws = r["montecarlo"].get("cpcv_weight_stability", {})
                info = ws.get(name, {})
                std = info.get("std", float("nan"))
                mean = info.get("mean", float("nan"))
                row += f"  {mean:.3f}±{std:.3f}".rjust(16)
            print(row)

        # Interpretation
        print(f"\n  Interpretación CPCV:")
        for r in results:
            mc = r["montecarlo"]
            mean_s = mc.get("cpcv_mean", 0)
            prob_neg = mc.get("cpcv_prob_neg", 1)
            p5 = mc.get("cpcv_p5", 0)
            verdict = "ROBUSTO" if mean_s > 0 and prob_neg < 0.30 and p5 > 0 else \
                      "ACEPTABLE" if mean_s > 0 and prob_neg < 0.50 else \
                      "FRÁGIL" if mean_s > 0 else "NO GENERALIZA"
            print(f"    {r['method']:>14s}: mean={mean_s:+.3f}  P(neg)={prob_neg:.1%}  p5={p5:+.3f}  → {verdict}")

    print("\n" + "=" * 100)


def _print_strategy_validation(strat_validation: dict):
    """Print CPCV and MC reshuffling for individual strategies."""
    print("\n" + "=" * 100)
    print("  VALIDACIÓN POR ESTRATEGIA (v12) — CPCV + MC Reshuffling")
    print("=" * 100)

    names = sorted(strat_validation.keys())
    short_names = {n: n.replace("Hypothesis", "").replace("Asym", "")[:25] for n in names}

    # CPCV table
    print(f"\n  CPCV (Combinatorial Purged Cross-Validation, Prado AFML Cap. 12):")
    print(f"  {'Estrategia':<27s} {'Mean':>8s} {'Std':>8s} {'p5':>8s} {'p25':>8s} {'p50':>8s} {'p75':>8s} {'p95':>8s}")
    print("  " + "-" * 91)
    for name in names:
        sv = strat_validation[name]
        pcts = sv["cpcv_percentiles"]
        print(f"  {short_names[name]:<27s} "
              f"{sv['cpcv_mean']:8.2f} {sv['cpcv_std']:8.2f} "
              f"{float(pcts.get('5', 0)):8.2f} {float(pcts.get('25', 0)):8.2f} "
              f"{float(pcts.get('50', 0)):8.2f} {float(pcts.get('75', 0)):8.2f} "
              f"{float(pcts.get('95', 0)):8.2f}")

    # CPCV Sharpe distribution (if available)
    print(f"\n  CPCV Sharpe Distribution por path:")
    for name in names:
        sv = strat_validation[name]
        cpcv_s = sv.get("cpcv_sharpe_dist")
        if cpcv_s is not None:
            if isinstance(cpcv_s, str):
                # pandas Series string repr — parse values
                import re
                vals = re.findall(r'[\d.]+\s+([\d.]+)', cpcv_s)
                vals = [float(v) for v in vals]
            elif hasattr(cpcv_s, 'values'):
                vals = list(cpcv_s.values)
            elif isinstance(cpcv_s, list):
                vals = cpcv_s
            else:
                vals = []
            if vals:
                arr = np.array(vals)
                print(f"    {short_names[name]:<27s} n_paths={len(arr)} "
                      f"mean={arr.mean():.2f} std={arr.std():.2f} "
                      f"min={arr.min():.2f} max={arr.max():.2f} "
                      f"all_positive={'YES' if arr.min() > 0 else 'NO'}")

    # MC Reshuffling table
    print(f"\n  MC RESHUFFLING (p-values — H0: la estrategia no es mejor que ruido):")
    print(f"  {'Estrategia':<27s} {'p(Sharpe)':>10s} {'p(MaxDD)':>10s} {'p(Return)':>10s} {'Signif':>8s}")
    print("  " + "-" * 70)
    for name in names:
        sv = strat_validation[name]
        ps = sv["mc_p_sharpe"]
        pd_ = sv["mc_p_maxdd"]
        pr_ = sv["mc_p_return"]
        sig = "***" if ps < 0.01 else "**" if ps < 0.05 else "*" if ps < 0.10 else "ns"
        print(f"  {short_names[name]:<27s} {ps:10.3f} {pd_:10.3f} {pr_:10.3f} {sig:>8s}")

    # MC CI for Sharpe
    print(f"\n  MC RESHUFFLING — CI Sharpe (percentiles de distribución nula):")
    print(f"  {'Estrategia':<27s} {'p5':>8s} {'p25':>8s} {'p50':>8s} {'p75':>8s} {'p95':>8s}")
    print("  " + "-" * 70)
    for name in names:
        sv = strat_validation[name]
        ci = sv["mc_ci_sharpe"]
        print(f"  {short_names[name]:<27s} "
              f"{float(ci.get('p5', 0)):8.3f} {float(ci.get('p25', 0)):8.3f} "
              f"{float(ci.get('p50', 0)):8.3f} {float(ci.get('p75', 0)):8.3f} "
              f"{float(ci.get('p95', 0)):8.3f}")

    # Fragility
    print(f"\n  FRAGILITY (fracción del retorno explicada por top-N días):")
    print(f"  {'Estrategia':<27s} {'Top1':>8s} {'Top3':>8s} {'Top5':>8s} {'Top10':>8s}")
    print("  " + "-" * 60)
    for name in names:
        sv = strat_validation[name]
        fr = sv["mc_fragility"]
        print(f"  {short_names[name]:<27s} "
              f"{float(fr.get('top1', 0)):8.1%} {float(fr.get('top3', 0)):8.1%} "
              f"{float(fr.get('top5', 0)):8.1%} {float(fr.get('top10', 0)):8.1%}")

    print("\n" + "=" * 100)


def _save_comparison(results: list[dict], out_dir: Path) -> Path:
    """Save comparison JSON."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"method_comparison_{ts}.json"

    def _num(x):
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (np.floating,)):
            return float(x)
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, pd.Series):
            return None  # skip series in JSON
        return x

    summary = {
        "timestamp": ts,
        "methods": [],
    }
    for r in results:
        entry = {
            "method": r["method"],
            "fdm": r["fdm"],
            "weights": r["weights"],
            "metrics": {k: _num(v) for k, v in r["metrics"].items()},
            "risk_attribution": r.get("risk_attribution"),
            "herfindahl_rc": r.get("_herfindahl"),
            "montecarlo": r.get("montecarlo", {}),
        }
        summary["methods"].append(entry)

    out_path.write_text(json.dumps(summary, indent=2, default=_num))
    return out_path


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path, default=_PORTFOLIO_OUT_DIR)
    args = ap.parse_args()

    print("[COMPARE] Cargando strategy results...")
    strategy_results = _load_strategy_results()
    if len(strategy_results) < 2:
        print(f"[COMPARE] ABORT: necesito >= 2 strategies, tengo {len(strategy_results)}")
        sys.exit(2)
    print(f"[COMPARE] {len(strategy_results)} estrategias cargadas")

    # Load strategy-level validation (CPCV + MC reshuffling)
    print("[COMPARE] Cargando validación por estrategia (CPCV + MC)...")
    strat_validation = _load_strategy_level_validation()
    print(f"[COMPARE] {len(strat_validation)} estrategias con validación")

    results = []
    for method in METHODS:
        print(f"\n[COMPARE] Corriendo: {method}...")
        r = _run_single_method(method, strategy_results)
        results.append(r)
        sharpe = r["metrics"].get("sharpe", 0.0)
        pv = r["montecarlo"].get("perm_p_value", -1)
        print(f"  -> Sharpe={sharpe:+.4f}  FDM={r['fdm']:.4f}  perm_p={pv:.3f}")

    _print_comparison(results, strategy_results)
    _print_strategy_validation(strat_validation)

    out_path = _save_comparison(results, args.output_dir)
    print(f"\n[COMPARE] JSON guardado en: {out_path}")


if __name__ == "__main__":
    main()
