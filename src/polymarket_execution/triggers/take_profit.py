"""Take-profit trigger monitor.

Built on top of ``StopLossMonitor``'s mechanic, but with a different predicate:
fires when the realised PnL crosses a profit target, instead of when price
crosses a level.

Why a separate module
---------------------
While the underlying loop is identical, the inputs differ: take-profit needs
to know entry price (or PnL directly), while stop-loss only needs current
price. Keeping them separate keeps the API obvious.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polymarket_execution.price_reference import PriceSource
from polymarket_execution.triggers.base import TriggerMonitor, TriggerSpec


@dataclass
class TakeProfitSpec(TriggerSpec):
    """A single take-profit trigger."""

    entry_price: float
    target_pnl_pct: float | None = None
    target_price: float | None = None


class TakeProfitMonitor(TriggerMonitor):
    """Monitor positions and fire market sells when profit target is reached."""

    def __init__(
        self,
        clob_client: Any,
        price_source: PriceSource,
        poll_interval_s: float = 0.5,
    ) -> None:
        super().__init__(clob_client, price_source, poll_interval_s)
        self._triggers: dict[str, TakeProfitSpec] = {}  # type: ignore[assignment]

    def add_take_profit(
        self,
        token_id: str,
        size: float,
        entry_price: float,
        target_pnl_pct: float | None = None,
        target_price: float | None = None,
    ) -> TakeProfitSpec:
        """Arm a take-profit trigger.

        Specify either ``target_pnl_pct`` (e.g., ``0.10`` for +10%) or
        ``target_price`` (absolute level). Exactly one is required.
        """
        if (target_pnl_pct is None) == (target_price is None):
            raise ValueError("Specify exactly one of target_pnl_pct or target_price")
        spec = TakeProfitSpec(
            token_id=token_id,
            size=size,
            entry_price=entry_price,
            target_pnl_pct=target_pnl_pct,
            target_price=target_price,
        )
        self._triggers[token_id] = spec
        return spec

    async def _evaluate(self, spec: TriggerSpec, current_price: float) -> bool:
        tp = spec
        if not isinstance(tp, TakeProfitSpec):
            return False
        if tp.target_price is not None:
            return current_price >= tp.target_price
        # target_pnl_pct path
        assert tp.target_pnl_pct is not None
        pnl_pct = (current_price - tp.entry_price) / tp.entry_price
        return pnl_pct >= tp.target_pnl_pct

    async def _dispatch_exit(self, spec: TriggerSpec) -> None:
        raise NotImplementedError(
            "take-profit exit dispatch is not implemented yet -- pending: place "
            "market exit via orders.place, wrapped with recovery layers"
        )
