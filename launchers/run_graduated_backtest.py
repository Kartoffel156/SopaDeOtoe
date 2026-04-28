"""
run_graduated_backtest.py — Primera corrida end-to-end del combinator
para la cohorte de estrategias graduadas el 2026-04-11.

Camino B (full re-run):
  1. Carga los 7 YAMLs en configs/graduated/.
  2. Corre SopaDeOtoe.core.runner.run_exploration (capa 1) — cada config
     dispara un subprocess con el pipeline v12 AFML completo.
  3. Por cada run exitoso, lee v12_run_dir/results.json y arma un
     StrategyResult: returns (resampleadas a daily), equity, positions
     proxy, signals, metrics.
  4. Carga PortfolioConfig desde config/portfolio_settings.yaml con
     overrides: target_volatility=None, MC n=1000 (primer pase rápido).
  5. Llama portfolio.runner.run_portfolio_backtest.
  6. Imprime reporte y guarda summary JSON en results/portfolio/.

Uso:
    cd Patacon/
    python -m SopaDeOtoe.launchers.run_graduated_backtest \
        [--n-jobs 4] [--skip-run] [--output-dir results/portfolio]

--skip-run omite la capa 1 y consume los v12_run_dir ya creados por una
corrida previa (leídos desde results/exploration/*.json).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
import numpy as np
import pandas as pd

import SopaDeOtoe._path_setup  # noqa: F401
import SopaDeOtoe.strategies  # noqa: F401 — triggers BaseStrategy._REGISTRY

from SopaDeOtoe.core.runner import run_exploration
from portfolio.data_structures import StrategyResult
from portfolio.portfolio_config import load_portfolio_config
from portfolio.runner import run_portfolio_backtest


_SOPA_DIR = Path(__file__).resolve().parent.parent
_GRADUATED_DIR = _SOPA_DIR / "configs" / "graduated"
_MANIFEST_PATH = _SOPA_DIR / "strategies" / "graduated_manifest.yaml"
_PORTFOLIO_CFG_PATH = _SOPA_DIR / "config" / "portfolio_settings.yaml"
_EXPLORATION_DIR = _SOPA_DIR / "results" / "exploration"
_PORTFOLIO_OUT_DIR = _SOPA_DIR / "results" / "portfolio"


def _load_graduated_configs() -> list[dict]:
    """Load the 7 graduated YAML configs as dicts ready for run_exploration."""
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text())
    configs = []
    for entry in manifest["strategies"]:
        yaml_path = _SOPA_DIR / entry["config_file"]
        cfg = yaml.safe_load(yaml_path.read_text())
        # run_exploration dispatches via 'ticker' presence; these YAMLs
        # already have ticker, so they'll be passed through as-is.
        # Stamp a unique config_id per run (avoid collisions on re-runs).
        cfg["config_id"] = f"{entry['strategy_class']}_{entry['run_id'].split('_')[-1]}_REPRO"
        cfg["_meta_run_id"] = entry["run_id"]
        cfg["_meta_strategy_class"] = entry["strategy_class"]
        cfg["_meta_config_hash"] = entry.get("config_hash", "")
        configs.append(cfg)
    return configs, manifest


def _results_to_strategy_result(
    name: str,
    run_dir: Path,
    n_trials: int = 1,
) -> StrategyResult:
    """
    Read a v12 results.json and build a StrategyResult for the portfolio
    combinator.

    Design choices:
    - returns resampleadas a daily: tomamos el último valor de equity por
      YYYY-MM-DD y calculamos pct_change(). Esto alinea con ann_factor=252.
    - positions proxy: (returns != 0). Suficiente para el masking de
      orthogonality y para portfolio_exposure. Se pierde el signo, pero
      ninguna función del combinator lee el signo de positions.
    - signals: mismo boolean proxy (no hay densidad confiable en v12 json).
    """
    data = json.loads((run_dir / "results.json").read_text())
    ec = data.get("equity_curve", {})
    dates = ec.get("dates", [])
    values = ec.get("values", [])
    if not values or not dates:
        raise ValueError(f"{name}: equity_curve vacío en {run_dir}")

    # Aggregate bars to daily (last equity per calendar day).
    raw = pd.DataFrame({"date": pd.to_datetime(dates), "eq": values})
    daily_eq = raw.groupby(raw["date"].dt.normalize())["eq"].last().sort_index()
    daily_eq.index.name = None

    returns = daily_eq.pct_change().fillna(0.0).astype(float)
    returns.name = name
    equity = daily_eq.astype(float)
    equity.name = name

    # Positions proxy: activity indicator.
    positions = (returns.abs() > 1e-12).astype(int)
    positions.name = name
    signals = positions.copy()
    signals.name = name

    raw_metrics = data.get("metrics", {}) or {}
    trade_stats = data.get("trade_stats", {}) or {}
    metrics = {
        "sharpe": float(raw_metrics.get("sharpe") or 0.0),
        "total_return": float(raw_metrics.get("total_return") or 0.0),
        "max_drawdown": float(raw_metrics.get("max_drawdown") or 0.0),
        "calmar": float(raw_metrics.get("calmar") or 0.0),
        "sortino": float(raw_metrics.get("sortino") or 0.0),
        "profit_factor": float(
            raw_metrics.get("profit_factor")
            or trade_stats.get("profit_factor")
            or 0.0
        ),
        "n_trades": int(
            trade_stats.get("total_trades")
            or trade_stats.get("n_trades")
            or raw_metrics.get("n_trades")
            or 0
        ),
    }

    return StrategyResult(
        name=name,
        returns=returns,
        equity=equity,
        positions=positions,
        signals=signals,
        metrics=metrics,
        extended_metrics=trade_stats,
        montecarlo=data.get("montecarlo", {}) or {},
        trades=data.get("backtest_trades", []) or [],
        meta={
            "n_trials": n_trials,
            "v12_run_dir": str(run_dir),
            "config_hash": (data.get("config", {}) or {}).get("config_hash"),
            "source_config_id": (data.get("config", {}) or {}).get("config_id"),
            "daily_bars": int(len(daily_eq)),
            "source_bars": int(len(values)),
        },
    )


def _load_portfolio_config_with_overrides():
    cfg = load_portfolio_config(_PORTFOLIO_CFG_PATH)
    # target_volatility comes from portfolio_settings.yaml — no override here.
    cfg.validation.n_permutations = 1000
    cfg.validation.n_bootstrap = 1000
    cfg.validation.run_stress_test = False  # acelera primera corrida
    cfg.validation.run_spa_test = False
    return cfg


def _print_report(portfolio_result, manifest):
    pr = portfolio_result
    names = pr.strategy_names
    n = len(names)
    w = pr.weights

    print("\n" + "=" * 72)
    print("  PORTFOLIO BACKTEST REPORT — first cohort 2026-04-11")
    print("=" * 72)
    print(f"  Method       : {pr.allocation_method}")
    print(f"  FDM          : {pr.fdm:.4f}")
    print(f"  Strategies   : {n}")
    print()
    print("  Weights (sum = {:.4f}):".format(float(w.sum())))
    for nm, wi in sorted(zip(names, w), key=lambda x: -x[1]):
        print(f"    {wi:6.3f}  {nm}")
    print()

    m = pr.metrics
    print("  Portfolio metrics:")
    for k in (
        "sharpe", "dsr", "annualized_return", "annualized_volatility",
        "max_drawdown", "calmar", "sortino", "diversification_ratio",
        "portfolio_volatility", "exposure",
    ):
        if k in m:
            v = m[k]
            print(f"    {k:25s} {v:+.4f}" if isinstance(v, float) else f"    {k:25s} {v}")
    print()

    ra = m.get("risk_attribution")
    if ra is not None:
        print("  Risk attribution (Roncalli Euler):")
        print(ra.to_string(index=False, float_format=lambda v: f"{v:+.4f}"))
        print()

    print("  Correlation matrix (Spearman, active-bars mask):")
    corr = pr.correlation
    print(corr.to_string(float_format=lambda v: f"{v:+.3f}"))
    print()

    orth = pr.orthogonality or {}
    eff_dim = orth.get("effective_dimension")
    pass_all = orth.get("pass_all_checks")
    eff_dim_str = f"{eff_dim:.3f}" if isinstance(eff_dim, (int, float)) else "n/a"
    print(f"  Orthogonality  : effective_dim={eff_dim_str}  pass_all={pass_all}")
    # Print any additional orthogonality diagnostics that are scalar.
    for k, v in orth.items():
        if k in ("effective_dimension", "pass_all_checks",
                 "correlation_matrix", "overlap_matrix"):
            continue
        if isinstance(v, (int, float)):
            print(f"    {k:25s} {v:+.4f}")
        elif isinstance(v, bool):
            print(f"    {k:25s} {v}")
    print()

    mc = pr.montecarlo
    if "permutation" in mc:
        p = mc["permutation"]
        print(
            "  Permutation    : p={:.4f}  obs_sharpe={:+.4f}".format(
                float(p.get("p_value", 0.0)),
                float(p.get("observed_sharpe", 0.0)),
            )
        )
    if "bootstrap" in mc:
        b = mc["bootstrap"]
        print(
            "  Bootstrap      : sharpe_5pct={:+.4f}  sharpe_95pct={:+.4f}".format(
                float(b.get("sharpe_5pct", 0.0)),
                float(b.get("sharpe_95pct", 0.0)),
            )
        )
    print()

    # Per-strategy vs. combined sharpe.
    print("  Per-strategy Sharpe (from v12 results.json):")
    for entry in manifest["strategies"]:
        cls = entry["strategy_class"]
        if cls in names:
            s = entry["metrics"]["sharpe"]
            print(f"    {s:+.4f}  {cls}")
    print(f"  Combined portfolio Sharpe: {m.get('sharpe', 0.0):+.4f}")
    print("=" * 72)


def _save_summary(portfolio_result, out_dir: Path, manifest) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"first_cohort_{ts}.json"

    pr = portfolio_result
    names = pr.strategy_names
    m = pr.metrics

    def _num(x):
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (np.floating, float)) and (np.isnan(x) or np.isinf(x)):
            return None
        if isinstance(x, (np.floating,)):
            return float(x)
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, pd.DataFrame):
            return x.to_dict()
        if isinstance(x, pd.Series):
            return x.to_dict()
        return x

    def _deep_convert(obj, _depth=0):
        """Recursively convert numpy/pandas types to JSON-safe primitives."""
        if _depth > 50:
            return str(obj)  # break infinite recursion
        if isinstance(obj, dict):
            return {str(k): _deep_convert(v, _depth + 1) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_deep_convert(v, _depth + 1) for v in obj]
        if isinstance(obj, pd.DataFrame):
            return _deep_convert(obj.to_dict(), _depth + 1)
        if isinstance(obj, pd.Series):
            return _deep_convert(obj.to_dict(), _depth + 1)
        return _num(obj)

    summary = {
        "timestamp": ts,
        "cohort": manifest.get("cohort"),
        "allocation_method": pr.allocation_method,
        "fdm": float(pr.fdm),
        "weights": {n: float(w) for n, w in zip(names, pr.weights)},
        "portfolio_metrics": {
            k: _num(v)
            for k, v in m.items()
            if k not in ("risk_attribution",)
        },
        "risk_attribution": (
            m["risk_attribution"].to_dict(orient="records")
            if "risk_attribution" in m
            else None
        ),
        "correlation": pr.correlation.round(6).to_dict(),
        "orthogonality": {
            k: _num(v)
            for k, v in pr.orthogonality.items()
            if k not in ("correlation_matrix", "overlap_matrix")
        },
        "montecarlo": {
            mc_k: {k: _num(v) for k, v in mc_v.items() if not isinstance(v, (list, np.ndarray)) or len(v) < 50}
            for mc_k, mc_v in pr.montecarlo.items()
            if isinstance(mc_v, dict)
        },
        "per_strategy_source": [
            {
                "name": sr.name,
                "v12_run_dir": sr.meta.get("v12_run_dir"),
                "source_metrics": sr.metrics,
                "daily_bars": sr.meta.get("daily_bars"),
            }
            for sr in pr.strategy_results
        ],
    }

    safe_summary = _deep_convert(summary)

    def _fallback(x):
        """Last-resort serializer for json.dumps."""
        try:
            return _num(x)
        except Exception:
            return str(x)

    out_path.write_text(json.dumps(safe_summary, indent=2, default=_fallback))
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-jobs", type=int, default=4)
    ap.add_argument(
        "--skip-run",
        action="store_true",
        help="Usar v12_run_dir ya existentes en results/exploration/*.json",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=_PORTFOLIO_OUT_DIR,
    )
    args = ap.parse_args()

    configs, manifest = _load_graduated_configs()
    print(f"[MAIN] Loaded {len(configs)} graduated configs from {_GRADUATED_DIR}")

    if args.skip_run:
        # Leer los results de la última exploración.
        print(f"[MAIN] --skip-run: leyendo resultados previos de {_EXPLORATION_DIR}")
        exploration_results = []
        for cfg in configs:
            cid = cfg["config_id"]
            path = _EXPLORATION_DIR / f"{cid}.json"
            if not path.exists():
                print(f"[MAIN] ERROR: {path} no existe. Corre sin --skip-run primero.")
                sys.exit(1)
            exploration_results.append(json.loads(path.read_text()))
    else:
        print(f"[MAIN] Ejecutando run_exploration (capa 1) con n_jobs={args.n_jobs}")
        exploration_results = run_exploration(
            configs,
            n_jobs=args.n_jobs,
            output_dir=_EXPLORATION_DIR,
        )

    # Build StrategyResults.
    print("\n[MAIN] Construyendo StrategyResult por cada run exitoso")
    strategy_results = []
    for cfg, res in zip(configs, exploration_results):
        if res.get("status") != "success":
            print(f"  SKIP {cfg['_meta_strategy_class']}: status={res.get('status')} "
                  f"error={res.get('error', '?')[:200]}")
            continue
        run_dir = Path(res["v12_run_dir"])
        cls = cfg["_meta_strategy_class"]
        # Use config_hash suffix to make name unique when same class appears multiple times.
        config_hash = cfg.get("_meta_config_hash") or cfg.get("config_hash", "")
        name = f"{cls}_{config_hash[:8]}" if config_hash else cls
        try:
            sr = _results_to_strategy_result(name, run_dir, n_trials=cfg.get("n_trials", 1))
        except Exception as e:
            print(f"  SKIP {cls}: error leyendo results.json — {type(e).__name__}: {e}")
            continue
        strategy_results.append(sr)
        print(f"  OK   {sr.name}: daily_bars={sr.meta['daily_bars']} "
              f"sharpe(raw)={sr.metrics['sharpe']:+.3f}")

    if len(strategy_results) < 2:
        print(f"\n[MAIN] ABORT: necesito >= 2 strategies, tengo {len(strategy_results)}")
        sys.exit(2)

    # Capa 2.
    print(f"\n[MAIN] Ejecutando run_portfolio_backtest con {len(strategy_results)} strategies")
    pcfg = _load_portfolio_config_with_overrides()
    pcfg.mode = "backtest"
    portfolio_result = run_portfolio_backtest(strategy_results, pcfg)

    _print_report(portfolio_result, manifest)
    out_path = _save_summary(portfolio_result, args.output_dir, manifest)
    print(f"\n[MAIN] Summary guardado en: {out_path}")


if __name__ == "__main__":
    main()
