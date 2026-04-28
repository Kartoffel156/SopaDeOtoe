"""
Load strategy configurations and trained models from disk.

Pipeline role: Bridge between saved individual strategy artifacts and
the portfolio combinator. Loads settings.yaml and pickled models.
"""

import pickle
from pathlib import Path
import yaml


def load_strategy_settings(path: Path | str) -> dict:
    """
    Load a strategy's settings.yaml and return as dict.

    Params:
        path: Path to the strategy's settings.yaml file.

    Returns:
        dict — raw settings for the strategy pipeline.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Strategy settings not found: {path}")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_strategy_model(path: Path | str | None):
    """
    Load a trained sklearn model from a pickle file.

    Params:
        path: Path to the .pkl file, or None if no pre-trained model.

    Returns:
        Trained model object, or None if path is None.

    Raises:
        FileNotFoundError: if path is given but file doesn't exist.
    """
    if path is None:
        return None
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)
