import pytest
from pathlib import Path
from portfolio.portfolio_config import (
    StrategyConfig, AllocationConfig, RiskConfig,
    ExecutionConfig, PortfolioConfig, load_portfolio_config,
)


def test_strategy_config_defaults():
    sc = StrategyConfig(
        name="test",
        settings_path="config/settings.yaml",
        asset="BTC-USD",
        interval="1d",
        market_type="crypto",
    )
    assert sc.enabled is True
    assert sc.model_path is None
    assert sc.bar_type == "time"


def test_portfolio_config_from_dict():
    raw = {
        "strategies": [
            {
                "name": "strat_a",
                "settings_path": "config/a.yaml",
                "asset": "BTC-USD",
                "interval": "4h",
                "market_type": "crypto",
            }
        ],
        "allocation": {"method": "erc"},
        "risk": {"target_volatility": 0.15},
        "execution": {"mode": "net_position"},
        "mode": "backtest",
        "backtest_period": {"start": "2024-01-01", "end": "2024-12-31"},
    }
    cfg = PortfolioConfig.from_dict(raw)
    assert len(cfg.strategies) == 1
    assert cfg.allocation.method == "erc"
    assert cfg.risk.target_volatility == 0.15
    assert cfg.execution.mode == "net_position"
    assert cfg.mode == "backtest"


def test_invalid_allocation_method_raises():
    raw = {
        "strategies": [{"name": "x", "settings_path": "y", "asset": "Z",
                        "interval": "1d", "market_type": "crypto"}],
        "allocation": {"method": "invalid_method"},
        "risk": {},
        "execution": {},
        "mode": "backtest",
    }
    with pytest.raises(ValueError, match="allocation.*method"):
        PortfolioConfig.from_dict(raw)


def test_load_portfolio_config_from_yaml(tmp_path):
    yaml_content = """
strategies:
  - name: "strat_btc"
    settings_path: "config/btc.yaml"
    asset: "BTC-USD"
    interval: "1d"
    market_type: "crypto"

allocation:
  method: "inverse_vol"
  rebalance_freq: "monthly"

risk:
  target_volatility: 0.20
  max_leverage: 2.0

execution:
  mode: "per_strategy"
  min_rebalance: 0.05

mode: "backtest"
backtest_period:
  start: "2024-01-01"
  end: "2024-06-30"
"""
    f = tmp_path / "portfolio_settings.yaml"
    f.write_text(yaml_content)
    cfg = load_portfolio_config(f)
    assert cfg.allocation.method == "inverse_vol"
    assert cfg.execution.mode == "per_strategy"
    assert cfg.risk.max_leverage == 2.0


def test_invalid_execution_mode_raises():
    raw = {
        "strategies": [],
        "allocation": {},
        "risk": {},
        "execution": {"mode": "bogus_mode"},
        "mode": "backtest",
    }
    with pytest.raises(ValueError, match="execution.mode"):
        PortfolioConfig.from_dict(raw)


def test_invalid_mode_raises():
    raw = {
        "strategies": [],
        "allocation": {},
        "risk": {},
        "execution": {},
        "mode": "paper_trading",  # not in {"backtest", "live"}
    }
    with pytest.raises(ValueError, match="^mode"):
        PortfolioConfig.from_dict(raw)
