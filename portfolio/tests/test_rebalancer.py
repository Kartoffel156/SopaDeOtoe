import pytest
from datetime import datetime, timedelta
from portfolio.rebalancer import should_rebalance, circuit_breaker_check


def test_time_based_rebalance_monthly():
    last = datetime(2024, 1, 15)
    now = datetime(2024, 2, 20)
    result, reason = should_rebalance(
        current_weights=[0.33, 0.33, 0.34],
        target_weights=[0.33, 0.33, 0.34],
        last_rebalance=last, now=now, rebalance_freq="monthly",
    )
    assert result is True
    assert "time" in reason.lower()


def test_no_rebalance_within_month():
    last = datetime(2024, 1, 15)
    now = datetime(2024, 1, 25)
    result, reason = should_rebalance(
        current_weights=[0.33, 0.33, 0.34],
        target_weights=[0.33, 0.33, 0.34],
        last_rebalance=last, now=now, rebalance_freq="monthly",
    )
    assert result is False


def test_drift_based_rebalance():
    last = datetime(2024, 1, 15)
    now = datetime(2024, 1, 20)  # within month
    result, reason = should_rebalance(
        current_weights=[0.50, 0.25, 0.25],  # drifted from target
        target_weights=[0.33, 0.33, 0.34],
        last_rebalance=last, now=now,
        rebalance_freq="monthly", drift_threshold=0.10,
    )
    assert result is True
    assert "drift" in reason.lower()


def test_circuit_breaker_no_trigger():
    action = circuit_breaker_check(
        current_dd=-0.05, threshold_1=0.10, threshold_2=0.15, kill_threshold=0.25,
    )
    assert action == "none"


def test_circuit_breaker_scale_50():
    action = circuit_breaker_check(
        current_dd=-0.12, threshold_1=0.10, threshold_2=0.15, kill_threshold=0.25,
    )
    assert action == "scale_50"


def test_circuit_breaker_scale_25():
    action = circuit_breaker_check(
        current_dd=-0.18, threshold_1=0.10, threshold_2=0.15, kill_threshold=0.25,
    )
    assert action == "scale_25"


def test_circuit_breaker_kill():
    action = circuit_breaker_check(
        current_dd=-0.30, threshold_1=0.10, threshold_2=0.15, kill_threshold=0.25,
    )
    assert action == "kill"
