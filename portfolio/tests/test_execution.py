import pytest
from portfolio.execution import NetPositionExecutor, PerStrategyExecutor


# --- NetPositionExecutor ---

def test_net_executor_open_from_flat():
    ex = NetPositionExecutor(min_rebalance=0.01)
    orders = ex.update("BTC", target=0.30, strategy_sources=["A"])
    assert len(orders) == 1
    assert orders[0]["action"] == "OPEN"
    assert orders[0]["size"] == 0.30


def test_net_executor_update_existing():
    ex = NetPositionExecutor(min_rebalance=0.01)
    ex.update("BTC", target=0.30, strategy_sources=["A"])
    orders = ex.update("BTC", target=0.50, strategy_sources=["A", "C"])
    assert len(orders) == 2  # CLOSE old + OPEN new
    assert orders[0]["action"] == "CLOSE"
    assert orders[1]["action"] == "OPEN"
    assert orders[1]["size"] == 0.50


def test_net_executor_close_to_flat():
    ex = NetPositionExecutor(min_rebalance=0.01)
    ex.update("BTC", target=0.30, strategy_sources=["A"])
    orders = ex.update("BTC", target=0.0, strategy_sources=[])
    assert len(orders) == 1
    assert orders[0]["action"] == "CLOSE"
    assert orders[0]["reason"] == "all_signals_flat"


def test_net_executor_no_action_below_min_rebalance():
    ex = NetPositionExecutor(min_rebalance=0.05)
    ex.update("BTC", target=0.30, strategy_sources=["A"])
    orders = ex.update("BTC", target=0.32, strategy_sources=["A"])
    assert len(orders) == 0  # 0.02 change < 0.05 threshold


def test_net_executor_cancel_all():
    ex = NetPositionExecutor(min_rebalance=0.01)
    ex.update("BTC", target=0.30, strategy_sources=["A"])
    ex.update("ETH", target=0.20, strategy_sources=["B"])
    orders = ex.cancel_all("circuit_breaker")
    assert len(orders) == 2
    assert all(o["action"] == "CLOSE" for o in orders)
    assert all(o["reason"] == "circuit_breaker" for o in orders)


# --- PerStrategyExecutor ---

def test_per_strategy_two_strategies_same_asset():
    ex = PerStrategyExecutor(min_rebalance=0.01)
    orders_a = ex.on_signal("A", "BTC", 1, 0.6, "signal_entry")
    orders_c = ex.on_signal("C", "BTC", 1, 0.5, "signal_entry")
    assert len(orders_a) == 1 and orders_a[0]["action"] == "OPEN"
    assert len(orders_c) == 1 and orders_c[0]["action"] == "OPEN"
    assert len(ex.get_open_orders()) == 2


def test_per_strategy_same_strategy_replaces():
    ex = PerStrategyExecutor(min_rebalance=0.01)
    ex.on_signal("A", "BTC", 1, 0.6, "signal_entry")
    orders = ex.on_signal("A", "BTC", 1, 0.8, "signal_update")
    assert len(orders) == 2  # CLOSE old + OPEN new
    assert len(ex.get_open_orders()) == 1  # still only 1 from strategy A


def test_per_strategy_signal_flat_closes_only_that_strategy():
    ex = PerStrategyExecutor(min_rebalance=0.01)
    ex.on_signal("A", "BTC", 1, 0.6, "signal_entry")
    ex.on_signal("C", "BTC", 1, 0.5, "signal_entry")
    orders = ex.on_signal("A", "BTC", 0, 0.0, "signal_flat")
    assert len(orders) == 1
    assert orders[0]["action"] == "CLOSE"
    assert orders[0]["strategy"] == "A"
    assert len(ex.get_open_orders()) == 1  # C still open


def test_per_strategy_cancel_all():
    ex = PerStrategyExecutor(min_rebalance=0.01)
    ex.on_signal("A", "BTC", 1, 0.6, "signal_entry")
    ex.on_signal("B", "ETH", -1, 0.4, "signal_entry")
    orders = ex.cancel_all("circuit_breaker")
    assert len(orders) == 2
    assert len(ex.get_open_orders()) == 0


def test_per_strategy_cancel_strategy():
    ex = PerStrategyExecutor(min_rebalance=0.01)
    ex.on_signal("A", "BTC", 1, 0.6, "signal_entry")
    ex.on_signal("B", "BTC", -1, 0.3, "signal_entry")
    orders = ex.cancel_strategy("A", "strategy_disabled")
    assert len(orders) == 1
    assert orders[0]["strategy"] == "A"
    assert len(ex.get_open_orders()) == 1  # B still open


def test_net_executor_get_open_positions_snapshot():
    ex = NetPositionExecutor(min_rebalance=0.01)
    ex.update("BTC", target=0.30, strategy_sources=["A"])
    snap = ex.get_open_positions()
    assert "BTC" in snap
    assert snap["BTC"]["size"] == 0.30
    # Adding to snapshot does not affect internal state (shallow copy)
    snap["ETH"] = {"size": 1.0}
    assert "ETH" not in ex.positions


def test_per_strategy_no_change_when_same_size_and_direction():
    """If new signal matches existing within min_rebalance and same direction, no orders."""
    ex = PerStrategyExecutor(min_rebalance=0.05)
    ex.on_signal("A", "BTC", 1, 0.60, "signal_entry")
    orders = ex.on_signal("A", "BTC", 1, 0.61, "signal_update")
    assert orders == []
    assert len(ex.get_open_orders()) == 1


def test_per_strategy_net_exposure_sums_by_asset():
    ex = PerStrategyExecutor(min_rebalance=0.01)
    ex.on_signal("A", "BTC", 1, 0.40, "signal_entry")
    ex.on_signal("B", "BTC", -1, 0.10, "signal_entry")
    ex.on_signal("C", "ETH", 1, 0.25, "signal_entry")
    assert abs(ex.net_exposure("BTC") - (0.40 - 0.10)) < 1e-12
    assert abs(ex.net_exposure("ETH") - 0.25) < 1e-12
    assert ex.net_exposure("SOL") == 0.0
