"""
Execution modes for the portfolio combinator.

Mode A (NetPositionExecutor): One position per asset — orthodox Carver/Roncalli.
Mode B (PerStrategyExecutor): One order per strategy per asset — audit-friendly.
"""

from datetime import datetime, timezone


class NetPositionExecutor:
    """
    One net position per asset. Carver Cap. 10-11 orthodox approach.

    State: {asset: {"size": float, "direction": str, "sources": list}}
    """

    def __init__(self, min_rebalance: float = 0.05):
        self.min_rebalance = min_rebalance
        self.positions: dict[str, dict] = {}
        self.closed_orders: list[dict] = []

    def update(self, asset: str, target: float,
               strategy_sources: list[str],
               reason: str = "signal_update") -> list[dict]:
        orders = []
        current = self.positions.get(asset)
        current_size = current["size"] if current else 0.0

        # Close to flat
        if abs(target) < 1e-10:
            if current:
                close_order = {
                    "action": "CLOSE", "asset": asset,
                    "size": current["size"],
                    "reason": "all_signals_flat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                orders.append(close_order)
                self.closed_orders.append(close_order)
                del self.positions[asset]
            return orders

        # Check min_rebalance threshold
        if abs(target - current_size) < self.min_rebalance:
            return orders

        # Close existing if present
        if current:
            close_order = {
                "action": "CLOSE", "asset": asset,
                "size": current["size"],
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            orders.append(close_order)
            self.closed_orders.append(close_order)

        # Open new
        direction = "long" if target > 0 else "short"
        open_order = {
            "action": "OPEN", "asset": asset,
            "direction": direction,
            "size": abs(target),
            "sources": strategy_sources,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        orders.append(open_order)
        self.positions[asset] = {
            "size": target, "direction": direction, "sources": strategy_sources,
        }
        return orders

    def cancel_all(self, reason: str) -> list[dict]:
        orders = []
        for asset, pos in list(self.positions.items()):
            close_order = {
                "action": "CLOSE", "asset": asset,
                "size": pos["size"], "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            orders.append(close_order)
            self.closed_orders.append(close_order)
        self.positions.clear()
        return orders

    def get_open_positions(self) -> dict:
        return dict(self.positions)


class PerStrategyExecutor:
    """
    One order per strategy per asset. Audit-friendly mode.

    Rule: (strategy, asset) = max one open order.
    Multiple strategies can have orders on same asset simultaneously.
    """

    def __init__(self, min_rebalance: float = 0.05):
        self.min_rebalance = min_rebalance
        self._next_id = 1
        self.open_orders: list[dict] = []
        self.closed_orders: list[dict] = []

    def _find_order(self, strategy: str, asset: str) -> dict | None:
        for o in self.open_orders:
            if o["strategy"] == strategy and o["asset"] == asset:
                return o
        return None

    def _close_order(self, order: dict, reason: str) -> dict:
        order["close_time"] = datetime.now(timezone.utc).isoformat()
        order["close_reason"] = reason
        self.open_orders.remove(order)
        self.closed_orders.append(order)
        return {
            "action": "CLOSE", "id": order["id"],
            "asset": order["asset"], "strategy": order["strategy"],
            "size": order["size"], "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def on_signal(self, strategy: str, asset: str,
                  direction: int, size: float, reason: str) -> list[dict]:
        orders = []
        existing = self._find_order(strategy, asset)

        # Signal flat -> close existing if any
        if direction == 0 or abs(size) < 1e-10:
            if existing:
                orders.append(self._close_order(existing, "signal_flat"))
            return orders

        # Has existing -> check if needs update
        if existing:
            if abs(size - existing["size"]) < self.min_rebalance and \
               direction == existing["direction"]:
                return orders  # no meaningful change
            orders.append(self._close_order(existing, reason))

        # Open new
        oid = self._next_id
        self._next_id += 1
        new_order = {
            "id": oid, "asset": asset, "strategy": strategy,
            "direction": direction, "size": size,
            "reason": reason,
            "open_time": datetime.now(timezone.utc).isoformat(),
        }
        self.open_orders.append(new_order)
        orders.append({
            "action": "OPEN", "id": oid, "asset": asset,
            "strategy": strategy, "direction": direction,
            "size": size, "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return orders

    def cancel_all(self, reason: str) -> list[dict]:
        orders = []
        for o in list(self.open_orders):
            orders.append(self._close_order(o, reason))
        return orders

    def cancel_strategy(self, strategy: str, reason: str) -> list[dict]:
        orders = []
        for o in list(self.open_orders):
            if o["strategy"] == strategy:
                orders.append(self._close_order(o, reason))
        return orders

    def get_open_orders(self) -> list[dict]:
        return list(self.open_orders)

    def net_exposure(self, asset: str) -> float:
        total = 0.0
        for o in self.open_orders:
            if o["asset"] == asset:
                total += o["direction"] * o["size"]
        return total
