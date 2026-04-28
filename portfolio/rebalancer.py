"""
Rebalancing logic with drift detection and circuit breaker.

Carver Cap. 11: monthly rebalance default.
AFML Cap. 15: progressive drawdown control.
"""

import numpy as np
from datetime import datetime, timedelta

_FREQ_DAYS = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90}


def should_rebalance(
    current_weights: list | np.ndarray,
    target_weights: list | np.ndarray,
    last_rebalance: datetime,
    now: datetime,
    rebalance_freq: str = "monthly",
    drift_threshold: float = 0.10,
) -> tuple[bool, str]:
    """
    Two triggers: time-based and drift-based.
    Returns (should_rebalance, reason).
    """
    current = np.asarray(current_weights)
    target = np.asarray(target_weights)

    # Time-based check
    days_since = (now - last_rebalance).days
    freq_days = _FREQ_DAYS.get(rebalance_freq, 30)
    if days_since >= freq_days:
        return True, f"Time-based: {days_since} days since last rebalance (freq={rebalance_freq})"

    # Drift-based check
    max_drift = np.max(np.abs(current - target))
    if max_drift >= drift_threshold:
        return True, f"Drift-based: max weight drift {max_drift:.3f} >= {drift_threshold}"

    return False, "No rebalance needed"


def circuit_breaker_check(
    current_dd: float,
    threshold_1: float = 0.10,
    threshold_2: float = 0.15,
    kill_threshold: float = 0.25,
) -> str:
    """
    Check drawdown against circuit breaker levels.

    Returns: "none" | "scale_50" | "scale_25" | "kill"
    """
    abs_dd = abs(current_dd)
    if abs_dd >= kill_threshold:
        return "kill"
    elif abs_dd >= threshold_2:
        return "scale_25"
    elif abs_dd >= threshold_1:
        return "scale_50"
    return "none"
