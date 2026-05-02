"""Stop-loss trigger monitor.

Fires when the reference price falls **below** the configured trigger price
(for long positions) or rises above it (for short positions).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from polymarket_execution.price_reference import PriceSource
from polymarket_execution.triggers.base import TriggerMonitor, TriggerSpec


@dataclass
class StopLossSpec(TriggerSpec):
    """A single stop-loss trigger."""

    trigger_price: float
    side: Literal["long", "short"] = "long"


class StopLossMonitor(TriggerMonitor):
    """Monitor positions and fire market sells when the trigger price is crossed."""

    def __init__(
        self,
        clob_client: Any,
        price_source: PriceSource,
        poll_interval_s: float = 0.5,
    ) -> None:
        super().__init__(clob_client, price_source, poll_interval_s)
        self._triggers: dict[str, StopLossSpec] = {}  # type: ignore[assignment]

    def add_stop(
        self,
        token_id: str,
        trigger_price: float,
        size: float,
        side: Literal["long", "short"] = "long",
    ) -> StopLossSpec:
        """Arm a stop-loss for ``token_id`` at ``trigger_price``."""
        spec = StopLossSpec(token_id=token_id, size=size, trigger_price=trigger_price, side=side)
        self._triggers[token_id] = spec
        return spec

    async def _evaluate(self, spec: TriggerSpec, current_price: float) -> bool:
        sl = spec  # narrowing — see add_stop
        if not isinstance(sl, StopLossSpec):
            return False
        if sl.side == "long":
            return current_price <= sl.trigger_price
        return current_price >= sl.trigger_price

    async def _dispatch_exit(self, spec: TriggerSpec) -> None:
        raise NotImplementedError(
            "stop-loss exit dispatch is not implemented yet -- pending: place "
            "market exit via orders.place, with recovery layers wrapping the call"
        )
