"""
Configuration schema for the portfolio combinator layer.

Loads from portfolio_settings.yaml and validates all fields.
Provides defaults aligned with Carver/Roncalli/Prado recommendations.
"""

from dataclasses import dataclass, field
from pathlib import Path
import yaml

_VALID_ALLOC_METHODS = {"equal_weight", "inverse_vol", "erc", "risk_budget", "hrp", "handcraft"}
_VALID_EXEC_MODES = {"net_position", "per_strategy"}
_VALID_COV_METHODS = {"sample", "shrinkage", "exponential"}
_VALID_REBAL_FREQ = {"daily", "weekly", "monthly", "quarterly"}
_VALID_MODES = {"backtest", "live"}


@dataclass
class StrategyConfig:
    name: str
    settings_path: str
    asset: str
    interval: str
    market_type: str
    model_path: str | None = None
    bar_type: str = "time"
    bars_per_day: int | None = None
    enabled: bool = True


@dataclass
class AllocationConfig:
    method: str = "erc"
    rebalance_freq: str = "monthly"
    covariance_method: str = "shrinkage"
    covariance_halflife: int = 63
    custom_budgets: list | None = None


@dataclass
class RiskConfig:
    target_volatility: float | None = 0.15
    max_leverage: float = 2.0
    max_weight_single: float = 0.50
    min_weight: float = 0.05
    trading_capital: float = 100_000.0
    vol_targeting_ewma_span: int = 36


@dataclass
class ExecutionConfig:
    mode: str = "net_position"
    min_rebalance: float = 0.05
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold_1: float = 0.10
    circuit_breaker_threshold_2: float = 0.15
    circuit_breaker_kill: float = 0.25


@dataclass
class ValidationConfig:
    rf_rate: float = 0.045
    n_permutations: int = 10_000
    n_bootstrap: int = 10_000
    bootstrap_block_size: int = 21
    run_stress_test: bool = True
    run_spa_test: bool = True
    run_cpcv: bool = True
    cpcv_n_groups: int = 6
    cpcv_n_test_groups: int = 2
    cpcv_embargo_pct: float = 0.01
    random_state: int | None = 42


@dataclass
class OrthogonalityConfig:
    max_correlation: float = 0.60
    min_effective_dimension_ratio: float = 0.70
    max_overlap: float = 0.50


@dataclass
class PortfolioConfig:
    strategies: list
    allocation: AllocationConfig
    risk: RiskConfig
    execution: ExecutionConfig
    mode: str
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    orthogonality: OrthogonalityConfig = field(default_factory=OrthogonalityConfig)
    backtest_period: dict | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> "PortfolioConfig":
        strategies = [StrategyConfig(**s) for s in raw.get("strategies", [])]
        alloc = AllocationConfig(**raw.get("allocation", {}))
        risk = RiskConfig(**raw.get("risk", {}))
        execution = ExecutionConfig(**raw.get("execution", {}))
        validation = ValidationConfig(**raw.get("validation", {}))
        orthogonality = OrthogonalityConfig(**raw.get("orthogonality", {}))
        mode = raw.get("mode", "backtest")

        # Validate enums
        if alloc.method not in _VALID_ALLOC_METHODS:
            raise ValueError(f"allocation.method must be one of {_VALID_ALLOC_METHODS}, got '{alloc.method}'")
        if execution.mode not in _VALID_EXEC_MODES:
            raise ValueError(f"execution.mode must be one of {_VALID_EXEC_MODES}, got '{execution.mode}'")
        if mode not in _VALID_MODES:
            raise ValueError(f"mode must be one of {_VALID_MODES}, got '{mode}'")

        return cls(
            strategies=strategies,
            allocation=alloc,
            risk=risk,
            execution=execution,
            validation=validation,
            orthogonality=orthogonality,
            mode=mode,
            backtest_period=raw.get("backtest_period"),
        )


def load_portfolio_config(path: Path | str) -> PortfolioConfig:
    """Load PortfolioConfig from a YAML file."""
    path = Path(path)
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    return PortfolioConfig.from_dict(raw)
