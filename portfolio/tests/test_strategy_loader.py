import pytest
import pickle
from pathlib import Path
from unittest.mock import MagicMock
from portfolio.strategy_loader import load_strategy_model, load_strategy_settings


def test_load_strategy_settings(tmp_path):
    """Load a strategy's settings.yaml and return dict."""
    settings = {"ticker": "BTC-USD", "interval": "4h", "strategy": {"name": "EMACrossover"}}
    f = tmp_path / "settings.yaml"
    import yaml
    f.write_text(yaml.dump(settings))

    result = load_strategy_settings(f)
    assert result["ticker"] == "BTC-USD"
    assert result["strategy"]["name"] == "EMACrossover"


def test_load_strategy_model(tmp_path):
    """Load a pickled object from disk."""
    fake_model = {"type": "model", "params": [1, 2, 3]}
    model_path = tmp_path / "model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(fake_model, f)

    model = load_strategy_model(model_path)
    assert model["type"] == "model"
    assert model["params"] == [1, 2, 3]


def test_load_strategy_model_none_path():
    """When model_path is None, return None (strategy will train from scratch)."""
    model = load_strategy_model(None)
    assert model is None


def test_load_strategy_model_missing_file():
    """When file doesn't exist, raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_strategy_model(Path("/nonexistent/model.pkl"))


def test_load_strategy_settings_missing_file():
    """load_strategy_settings raises if path does not exist."""
    with pytest.raises(FileNotFoundError, match="Strategy settings not found"):
        load_strategy_settings(Path("/nonexistent/settings.yaml"))
