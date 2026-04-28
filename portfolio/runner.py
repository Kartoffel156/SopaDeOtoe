"""
Portfolio runner — orchestrator for backtest and live modes.

Connects all portfolio modules end-to-end:
config -> strategy loader -> orthogonality -> weights -> combinator
-> vol targeting -> execution -> signal emitter -> metrics -> montecarlo.

Spec reference: multi_strategy_combinator.md Section 5.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timezone

from portfolio.data_structures import StrategyResult, PortfolioSignal
from portfolio.portfolio_config import PortfolioConfig
from portfolio.strategy_loader import load_strategy_settings, load_strategy_model
from portfolio.orthogonality import orthogonality_report
from portfolio.covariance import estimate_covariance
from portfolio.risk_budget import (
    equal_weight, inverse_volatility, equal_risk_contribution,
    risk_budget_solve, hierarchical_risk_parity,
)
from portfolio.combinator import (
    forecast_diversification_multiplier, combine_weighted_returns,
)
from portfolio.vol_targeting import apply_vol_targeting
from portfolio.execution import NetPositionExecutor, PerStrategyExecutor
from portfolio.signal_emitter import SignalEmitter
from portfolio.rebalancer import should_rebalance, circuit_breaker_check
from portfolio.portfolio_metrics import compute_portfolio_metrics
from portfolio.portfolio_montecarlo import (
    strategy_permutation, portfolio_bootstrap,
    correlation_stress_test, portfolio_spa_test,
    portfolio_cpcv,
)


@dataclass
class PortfolioResult:
    """Complete output of a portfolio backtest or live session."""
    # Strategy-level
    strategy_results: list[StrategyResult]
    strategy_names: list[str]

    # Orthogonality
    orthogonality: dict

    # Weights & combination
    weights: np.ndarray
    allocation_method: str
    fdm: float
    covariance: np.ndarray
    correlation: pd.DataFrame

    # Combined series
    combined_returns: pd.Series
    combined_equity: pd.Series
    returns_df: pd.DataFrame

    # Metrics
    metrics: dict

    # Monte Carlo validation
    montecarlo: dict

    # Signals
    signals: list[PortfolioSignal]

    # Config
    config: PortfolioConfig


def _compute_weights(method: str,
                     covariance: np.ndarray,
                     correlation: np.ndarray,
                     volatilities: np.ndarray,
                     n: int,
                     custom_budgets: list | None = None) -> np.ndarray:
    """Dispatch to the appropriate weight allocation method."""
    if method == "equal_weight":
        return equal_weight(n)
    elif method == "inverse_vol":
        return inverse_volatility(volatilities)
    elif method == "erc":
        return equal_risk_contribution(covariance)
    elif method == "risk_budget":
        budgets = np.array(custom_budgets) if custom_budgets else equal_weight(n)
        return risk_budget_solve(covariance, budgets)
    elif method == "hrp":
        return hierarchical_risk_parity(covariance, correlation)
    else:
        return equal_weight(n)


def _apply_weight_constraints(weights: np.ndarray,
                              max_weight: float,
                              min_weight: float,
                              max_iter: int = 20) -> np.ndarray:
    """Clip weights to [min_weight, max_weight] and renormalize iteratively."""
    w = weights.copy()
    for _ in range(max_iter):
        w = np.clip(w, min_weight, max_weight)
        s = w.sum()
        if s > 0:
            w = w / s
        if w.max() <= max_weight + 1e-10 and w.min() >= min_weight - 1e-10:
            break
    return w


def run_portfolio_backtest(
    strategy_results: list[StrategyResult],
    config: PortfolioConfig,
) -> PortfolioResult:
    """
    Full portfolio backtest pipeline from pre-computed strategy results.

    Steps:
    1. Align all strategy return series to common DatetimeIndex
    2. Run orthogonality_report()
    3. Estimate covariance matrix
    4. Compute weights via allocation_method
    5. Compute FDM (Carver Cap. 8)
    6. Combine returns: R_p(t) = FDM x sum(w_i x R_i(t))
    7. If target_volatility: apply vol-targeting overlay
    8. Compute portfolio metrics
    9. Run Monte Carlo validation
    10. Package into PortfolioResult
    """
    names = [sr.name for sr in strategy_results]
    n = len(strategy_results)

    # 1. Align returns to common index
    returns_df = pd.DataFrame(
        {sr.name: sr.returns for sr in strategy_results}
    ).fillna(0.0)

    positions_df = pd.DataFrame(
        {sr.name: sr.positions for sr in strategy_results}
    ).fillna(0.0)

    # 2. Orthogonality
    orth = orthogonality_report(
        returns_df, positions_df,
        max_correlation=config.orthogonality.max_correlation,
        max_overlap=config.orthogonality.max_overlap,
        min_dim_ratio=config.orthogonality.min_effective_dimension_ratio,
    )
    corr = orth["correlation_matrix"]

    # 3. Covariance
    cov = estimate_covariance(
        returns_df,
        method=config.allocation.covariance_method,
        halflife=config.allocation.covariance_halflife,
    )
    vols = np.sqrt(np.diag(cov))

    # 4. Weights
    weights = _compute_weights(
        config.allocation.method, cov, corr.values, vols, n,
        config.allocation.custom_budgets,
    )
    weights = _apply_weight_constraints(
        weights,
        config.risk.max_weight_single,
        config.risk.min_weight,
    )

    # 5. FDM
    fdm = forecast_diversification_multiplier(weights, corr.values)

    # 6. Combine returns
    combined = combine_weighted_returns(returns_df, weights, fdm)

    # 7. Vol targeting
    if config.risk.target_volatility is not None:
        combined = apply_vol_targeting(
            combined,
            target_vol=config.risk.target_volatility,
            max_leverage=config.risk.max_leverage,
            ewma_span=config.risk.vol_targeting_ewma_span,
        )

    combined_equity = (1 + combined).cumprod()

    # 8. Metrics
    n_trials = [sr.meta.get("n_trials", 1) for sr in strategy_results]
    metrics = compute_portfolio_metrics(
        combined, weights, cov, names,
        positions_df=positions_df,
        rf_rate=config.validation.rf_rate,
        n_strategies=n,
        n_trials_per_strategy=n_trials,
    )

    # 9. Monte Carlo
    mc = {}
    mc["permutation"] = strategy_permutation(
        returns_df, weights,
        n_permutations=config.validation.n_permutations,
        random_state=config.validation.random_state,
    )
    mc["bootstrap"] = portfolio_bootstrap(
        combined,
        n_bootstrap=config.validation.n_bootstrap,
        block_size=config.validation.bootstrap_block_size,
        random_state=config.validation.random_state,
    )
    if config.validation.run_stress_test:
        mc["stress_test"] = correlation_stress_test(
            returns_df, weights,
            random_state=config.validation.random_state,
        )
    if config.validation.run_spa_test:
        mc["spa"] = portfolio_spa_test(
            combined,
            n_bootstrap=config.validation.n_bootstrap,
            random_state=config.validation.random_state,
        )
    if config.validation.run_cpcv:
        mc["cpcv"] = portfolio_cpcv(
            returns_df,
            allocation_method=config.allocation.method,
            covariance_method=config.allocation.covariance_method,
            covariance_halflife=config.allocation.covariance_halflife,
            n_groups=config.validation.cpcv_n_groups,
            n_test_groups=config.validation.cpcv_n_test_groups,
            embargo_pct=config.validation.cpcv_embargo_pct,
            max_weight=config.risk.max_weight_single,
            min_weight=config.risk.min_weight,
            target_volatility=config.risk.target_volatility,
            max_leverage=config.risk.max_leverage,
            custom_budgets=config.allocation.custom_budgets,
        )

    # 10. Signals (backtest replay via emitter)
    emitter = SignalEmitter(mode="backtest", trading_capital=config.risk.trading_capital)
    executor = NetPositionExecutor(min_rebalance=config.execution.min_rebalance) \
        if config.execution.mode == "net_position" \
        else PerStrategyExecutor(min_rebalance=config.execution.min_rebalance)

    signals_list = emitter.replay()

    return PortfolioResult(
        strategy_results=strategy_results,
        strategy_names=names,
        orthogonality=orth,
        weights=weights,
        allocation_method=config.allocation.method,
        fdm=fdm,
        covariance=cov,
        correlation=corr,
        combined_returns=combined,
        combined_equity=combined_equity,
        returns_df=returns_df,
        metrics=metrics,
        montecarlo=mc,
        signals=signals_list,
        config=config,
    )


class LivePortfolioRunner:
    """
    Event-driven runner for live mode.

    Maintains state between bars: positions, weights, covariance,
    vol estimate, FDM. Rebalances on schedule or drift detection.
    """

    def __init__(self, config: PortfolioConfig):
        self.config = config
        self.names = [s.name for s in config.strategies]
        self.n = len(self.names)

        # State
        self.weights = equal_weight(self.n)
        self.fdm = 1.0
        self.covariance = np.eye(self.n) * 0.01
        self.vol_realized = 0.15
        self.last_rebalance = datetime.now(timezone.utc)

        # Return history (for rolling covariance)
        self.return_history: dict[str, list[float]] = {n: [] for n in self.names}

        # Execution
        if config.execution.mode == "net_position":
            self.executor = NetPositionExecutor(
                min_rebalance=config.execution.min_rebalance)
        else:
            self.executor = PerStrategyExecutor(
                min_rebalance=config.execution.min_rebalance)

        self.emitter = SignalEmitter(
            mode="live",
            trading_capital=config.risk.trading_capital,
        )

        self.dd_current = 0.0
        self.equity_peak = config.risk.trading_capital
        self.equity_current = config.risk.trading_capital

    def on_new_bar(self, strategy_signals: dict[str, dict]) -> dict:
        """
        Process signals from all strategies for one bar.

        strategy_signals: {strategy_name: {"signal": int, "size": float,
                          "return": float, "price": float, "asset": str}}

        Returns dict with orders, rebalance info, circuit breaker status.
        """
        now = datetime.now(timezone.utc)
        all_orders = []
        bar_return = 0.0

        # Update return history
        for name in self.names:
            sig = strategy_signals.get(name, {})
            ret = sig.get("return", 0.0)
            self.return_history[name].append(ret)
            bar_return += self.weights[self.names.index(name)] * ret * self.fdm

        # Update equity tracking
        self.equity_current *= (1 + bar_return)
        self.equity_peak = max(self.equity_peak, self.equity_current)
        self.dd_current = (self.equity_current - self.equity_peak) / self.equity_peak

        # Circuit breaker check
        cb_action = circuit_breaker_check(
            self.dd_current,
            self.config.execution.circuit_breaker_threshold_1,
            self.config.execution.circuit_breaker_threshold_2,
            self.config.execution.circuit_breaker_kill,
        )

        if cb_action == "kill" and self.config.execution.circuit_breaker_enabled:
            if isinstance(self.executor, NetPositionExecutor):
                all_orders.extend(self.executor.cancel_all("circuit_breaker"))
            else:
                all_orders.extend(self.executor.cancel_all("circuit_breaker"))
            return {
                "orders": all_orders,
                "circuit_breaker": cb_action,
                "rebalance_triggered": False,
                "dd_current": self.dd_current,
            }

        # Process individual strategy signals
        for name in self.names:
            sig = strategy_signals.get(name, {})
            signal_val = sig.get("signal", 0)
            size = sig.get("size", 0.0)
            asset = sig.get("asset", "UNKNOWN")
            price = sig.get("price", 0.0)

            if isinstance(self.executor, NetPositionExecutor):
                idx = self.names.index(name)
                target = self.weights[idx] * signal_val * size * self.fdm
                orders = self.executor.update(asset, target, [name])
            else:
                orders = self.executor.on_signal(name, asset, signal_val, size, "signal_update")

            all_orders.extend(orders)

        # Check rebalance
        rebalanced = False
        current_w = self.weights.tolist()
        target_w = self.weights.tolist()  # same until recomputed
        rebal, reason = should_rebalance(
            current_w, target_w, self.last_rebalance, now,
            self.config.allocation.rebalance_freq,
        )
        if rebal:
            self._recompute_weights()
            self.last_rebalance = now
            rebalanced = True

        return {
            "orders": all_orders,
            "circuit_breaker": cb_action,
            "rebalance_triggered": rebalanced,
            "dd_current": self.dd_current,
            "weights": self.weights.tolist(),
            "fdm": self.fdm,
        }

    def _recompute_weights(self):
        """Re-estimate covariance, recompute weights and FDM."""
        min_history = 30
        if len(self.return_history[self.names[0]]) < min_history:
            return

        returns_df = pd.DataFrame(self.return_history)
        self.covariance = estimate_covariance(
            returns_df,
            method=self.config.allocation.covariance_method,
            halflife=self.config.allocation.covariance_halflife,
        )
        vols = np.sqrt(np.diag(self.covariance))
        corr = np.corrcoef(returns_df.values.T)

        self.weights = _compute_weights(
            self.config.allocation.method,
            self.covariance, corr, vols, self.n,
            self.config.allocation.custom_budgets,
        )
        self.weights = _apply_weight_constraints(
            self.weights,
            self.config.risk.max_weight_single,
            self.config.risk.min_weight,
        )
        self.fdm = forecast_diversification_multiplier(self.weights, corr)

    def force_rebalance(self) -> dict:
        """Manual rebalance trigger."""
        self._recompute_weights()
        self.last_rebalance = datetime.now(timezone.utc)
        return {
            "weights": self.weights.tolist(),
            "fdm": self.fdm,
        }

    def get_portfolio_state(self) -> dict:
        """Current snapshot of portfolio state."""
        return {
            "weights": self.weights.tolist(),
            "fdm": self.fdm,
            "dd_current": self.dd_current,
            "equity_current": self.equity_current,
            "equity_peak": self.equity_peak,
            "vol_realized": self.vol_realized,
            "last_rebalance": self.last_rebalance.isoformat(),
            "n_bars_processed": len(self.return_history[self.names[0]]) if self.names else 0,
        }
