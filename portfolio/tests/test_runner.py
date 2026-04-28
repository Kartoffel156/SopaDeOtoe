import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from portfolio.runner import (
    run_portfolio_backtest, PortfolioResult,
    LivePortfolioRunner, _compute_weights, _apply_weight_constraints,
)
from portfolio.execution import PerStrategyExecutor
from portfolio.data_structures import StrategyResult
from portfolio.portfolio_config import (
    PortfolioConfig, StrategyConfig, AllocationConfig,
    RiskConfig, ExecutionConfig, ValidationConfig, OrthogonalityConfig,
)


def _make_strategy_result(name, n=500, seed=42, mean_ret=0.0003):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    returns = pd.Series(rng.normal(mean_ret, 0.01, n), index=idx)
    equity = (1 + returns).cumprod() * 100
    positions = pd.Series(rng.choice([-1, 0, 1], n, p=[0.2, 0.5, 0.3]), index=idx)
    signals = pd.Series(rng.choice([-1, 0, 1], n, p=[0.15, 0.7, 0.15]), index=idx)
    return StrategyResult(
        name=name, returns=returns, equity=equity,
        positions=positions, signals=signals,
        metrics={"sharpe": 1.0}, extended_metrics={},
        montecarlo={}, trades=[],
        meta={"asset": "BTC-USD", "interval": "1d",
              "market_type": "crypto", "n_trials": 1},
    )


def _make_config(n_strategies=3):
    strategies = [
        StrategyConfig(name=f"strat_{i}", settings_path=f"config/{i}.yaml",
                       asset="BTC-USD", interval="1d", market_type="crypto")
        for i in range(n_strategies)
    ]
    return PortfolioConfig(
        strategies=strategies,
        allocation=AllocationConfig(method="erc", covariance_method="sample"),
        risk=RiskConfig(target_volatility=0.15, max_leverage=2.0,
                        max_weight_single=0.60, min_weight=0.05),
        execution=ExecutionConfig(mode="net_position", min_rebalance=0.05),
        validation=ValidationConfig(
            n_permutations=100, n_bootstrap=100,
            run_stress_test=False, run_spa_test=False,
            random_state=42,
        ),
        orthogonality=OrthogonalityConfig(),
        mode="backtest",
    )


# --- Weight helpers ---

def test_compute_weights_equal():
    w = _compute_weights("equal_weight", np.eye(3), np.eye(3),
                         np.array([0.1, 0.1, 0.1]), 3)
    assert np.allclose(w, 1/3)


def test_compute_weights_inverse_vol():
    vols = np.array([0.1, 0.2, 0.4])
    w = _compute_weights("inverse_vol", np.diag(vols**2), np.eye(3), vols, 3)
    assert w[0] > w[1] > w[2]


def test_apply_weight_constraints():
    w = np.array([0.7, 0.2, 0.1])
    w_clipped = _apply_weight_constraints(w, max_weight=0.5, min_weight=0.1)
    assert w_clipped.max() <= 0.5 + 1e-6
    assert w_clipped.min() >= 0.1 - 1e-6
    assert abs(w_clipped.sum() - 1.0) < 1e-6


# --- Backtest runner ---

def test_run_portfolio_backtest_returns_result():
    results = [
        _make_strategy_result("A", seed=42),
        _make_strategy_result("B", seed=43),
        _make_strategy_result("C", seed=44),
    ]
    config = _make_config(3)
    pr = run_portfolio_backtest(results, config)
    assert isinstance(pr, PortfolioResult)
    assert len(pr.strategy_names) == 3
    assert len(pr.combined_returns) == 500


def test_run_portfolio_backtest_weights_sum_to_one():
    results = [
        _make_strategy_result("A", seed=42),
        _make_strategy_result("B", seed=43),
    ]
    config = _make_config(2)
    pr = run_portfolio_backtest(results, config)
    assert abs(pr.weights.sum() - 1.0) < 1e-6


def test_run_portfolio_backtest_has_metrics():
    results = [
        _make_strategy_result("A", seed=42),
        _make_strategy_result("B", seed=43),
    ]
    config = _make_config(2)
    pr = run_portfolio_backtest(results, config)
    assert "sharpe" in pr.metrics
    assert "dsr" in pr.metrics
    assert "max_drawdown" in pr.metrics


def test_run_portfolio_backtest_has_montecarlo():
    results = [
        _make_strategy_result("A", seed=42),
        _make_strategy_result("B", seed=43),
    ]
    config = _make_config(2)
    pr = run_portfolio_backtest(results, config)
    assert "permutation" in pr.montecarlo
    assert "bootstrap" in pr.montecarlo


def test_run_portfolio_backtest_fdm_reasonable():
    results = [
        _make_strategy_result("A", seed=42),
        _make_strategy_result("B", seed=43),
        _make_strategy_result("C", seed=44),
    ]
    config = _make_config(3)
    pr = run_portfolio_backtest(results, config)
    assert 1.0 <= pr.fdm <= 2.5


# --- Live runner ---

def test_live_runner_init():
    config = _make_config(2)
    runner = LivePortfolioRunner(config)
    assert runner.n == 2
    assert len(runner.weights) == 2


def test_live_runner_on_new_bar():
    config = _make_config(2)
    runner = LivePortfolioRunner(config)
    result = runner.on_new_bar({
        "strat_0": {"signal": 1, "size": 0.5, "return": 0.01,
                     "price": 50000, "asset": "BTC"},
        "strat_1": {"signal": -1, "size": 0.3, "return": -0.005,
                     "price": 50000, "asset": "BTC"},
    })
    assert "orders" in result
    assert "circuit_breaker" in result
    assert "dd_current" in result


def test_live_runner_get_state():
    config = _make_config(2)
    runner = LivePortfolioRunner(config)
    state = runner.get_portfolio_state()
    assert "weights" in state
    assert "fdm" in state
    assert "dd_current" in state
    assert "equity_current" in state


def test_live_runner_force_rebalance():
    config = _make_config(2)
    runner = LivePortfolioRunner(config)
    rng = np.random.default_rng(7)
    # Feed enough bars so rebalance can work — noisy returns avoid zero-variance
    for i in range(50):
        runner.on_new_bar({
            "strat_0": {"signal": 1, "size": 0.5, "return": float(rng.normal(0.001, 0.01)),
                         "price": 50000, "asset": "BTC"},
            "strat_1": {"signal": 1, "size": 0.3, "return": float(rng.normal(0.0005, 0.01)),
                         "price": 50000, "asset": "BTC"},
        })
    result = runner.force_rebalance()
    assert "weights" in result
    assert "fdm" in result


def test_live_runner_circuit_breaker_kill():
    config = _make_config(2)
    runner = LivePortfolioRunner(config)
    # Simulate a massive loss
    runner.equity_current = 70_000  # 30% loss
    runner.equity_peak = 100_000
    runner.dd_current = -0.30
    result = runner.on_new_bar({
        "strat_0": {"signal": 1, "size": 0.5, "return": -0.05,
                     "price": 50000, "asset": "BTC"},
        "strat_1": {"signal": 1, "size": 0.3, "return": -0.05,
                     "price": 50000, "asset": "BTC"},
    })
    assert result["circuit_breaker"] == "kill"


# --- Additional weight dispatcher branches ---

def test_compute_weights_risk_budget():
    cov = np.array([[0.04, 0.006], [0.006, 0.09]])
    w = _compute_weights("risk_budget", cov, np.eye(2),
                         np.array([0.2, 0.3]), 2,
                         custom_budgets=[0.5, 0.5])
    assert abs(w.sum() - 1.0) < 1e-6


def test_compute_weights_risk_budget_default_budgets():
    """risk_budget without custom budgets falls back to equal_weight budgets."""
    cov = np.array([[0.04, 0.006], [0.006, 0.09]])
    w = _compute_weights("risk_budget", cov, np.eye(2),
                         np.array([0.2, 0.3]), 2, custom_budgets=None)
    assert abs(w.sum() - 1.0) < 1e-6


def test_compute_weights_hrp():
    cov = np.diag([0.01, 0.04, 0.09])
    corr = np.eye(3)
    w = _compute_weights("hrp", cov, corr, np.sqrt(np.diag(cov)), 3)
    assert abs(w.sum() - 1.0) < 1e-6


def test_compute_weights_unknown_falls_back_to_equal():
    w = _compute_weights("not_a_method", np.eye(3), np.eye(3),
                         np.array([0.1, 0.1, 0.1]), 3)
    assert np.allclose(w, 1/3)


# --- Backtest runner with stress test + SPA enabled ---

def test_run_portfolio_backtest_with_stress_and_spa():
    results = [
        _make_strategy_result("A", seed=42),
        _make_strategy_result("B", seed=43),
    ]
    config = _make_config(2)
    config.validation.run_stress_test = True
    config.validation.run_spa_test = True
    config.validation.n_bootstrap = 50
    pr = run_portfolio_backtest(results, config)
    assert "stress_test" in pr.montecarlo
    assert "spa" in pr.montecarlo


# --- Live runner: per_strategy execution branches ---

def _make_config_per_strategy(n_strategies=2):
    cfg = _make_config(n_strategies)
    cfg.execution.mode = "per_strategy"
    return cfg


def test_live_runner_per_strategy_executor_selected():
    config = _make_config_per_strategy(2)
    runner = LivePortfolioRunner(config)
    assert isinstance(runner.executor, PerStrategyExecutor)


def test_live_runner_per_strategy_on_new_bar():
    """Covers on_new_bar routing to PerStrategyExecutor.on_signal."""
    config = _make_config_per_strategy(2)
    runner = LivePortfolioRunner(config)
    result = runner.on_new_bar({
        "strat_0": {"signal": 1, "size": 0.5, "return": 0.001,
                     "price": 50000, "asset": "BTC"},
        "strat_1": {"signal": -1, "size": 0.3, "return": -0.001,
                     "price": 50000, "asset": "BTC"},
    })
    assert "orders" in result
    # Not killed — any non-kill status is acceptable
    assert result["circuit_breaker"] != "kill"


def test_live_runner_per_strategy_circuit_breaker_kill():
    """Kill path with PerStrategyExecutor — covers the else branch."""
    config = _make_config_per_strategy(2)
    runner = LivePortfolioRunner(config)
    runner.equity_current = 70_000
    runner.equity_peak = 100_000
    runner.dd_current = -0.30
    result = runner.on_new_bar({
        "strat_0": {"signal": 1, "size": 0.5, "return": -0.05,
                     "price": 50000, "asset": "BTC"},
        "strat_1": {"signal": 1, "size": 0.3, "return": -0.05,
                     "price": 50000, "asset": "BTC"},
    })
    assert result["circuit_breaker"] == "kill"


def test_live_runner_recompute_weights_early_return_on_short_history():
    """_recompute_weights bails out if history has fewer than min bars."""
    config = _make_config(2)
    runner = LivePortfolioRunner(config)
    w_before = runner.weights.copy()
    runner._recompute_weights()  # no history yet
    assert np.array_equal(runner.weights, w_before)


def test_live_runner_rebalance_triggered_on_new_bar():
    """Force should_rebalance to fire by backdating last_rebalance."""
    config = _make_config(2)
    config.allocation.rebalance_freq = "daily"
    runner = LivePortfolioRunner(config)
    rng = np.random.default_rng(123)
    # Feed enough history so _recompute_weights will run — use noisy returns
    # so covariance/correlation estimators have non-zero variance.
    for i in range(40):
        r0 = float(rng.normal(0.001, 0.01))
        r1 = float(rng.normal(0.0005, 0.01))
        runner.on_new_bar({
            "strat_0": {"signal": 1, "size": 0.5, "return": r0,
                         "price": 50000, "asset": "BTC"},
            "strat_1": {"signal": 1, "size": 0.3, "return": r1,
                         "price": 50000, "asset": "BTC"},
        })
    # Backdate to force rebalance
    runner.last_rebalance = datetime.now(timezone.utc) - timedelta(days=5)
    result = runner.on_new_bar({
        "strat_0": {"signal": 1, "size": 0.5, "return": float(rng.normal(0, 0.01)),
                     "price": 50000, "asset": "BTC"},
        "strat_1": {"signal": 1, "size": 0.3, "return": float(rng.normal(0, 0.01)),
                     "price": 50000, "asset": "BTC"},
    })
    assert result["rebalance_triggered"] is True
