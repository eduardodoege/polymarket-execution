"""Abstract trigger monitor — base for stop-loss and take-profit.

Mechanic:

1. Monitor maintains a registry of armed triggers per token_id.
2. On each tick (price update or PnL update), evaluate each trigger's predicate.
3. When a predicate returns True, dispatch an exit order via the executor.
4. Recovery layers (see ``polymarket_execution.recovery``) handle masked fills.

The library provides the **mechanic**: how to monitor and how to exit.
It does not provide the **decision** (which price counts, what threshold
to use, when to arm) — those are user-supplied via hooks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from polymarket_execution.price_reference import PriceSource


@dataclass
class TriggerSpec:
    """A single armed trigger. Subclasses extend with their own fields."""

    token_id: str
    size: float


class TriggerMonitor(ABC):
    """Async monitor that evaluates triggers on each tick and dispatches exits."""

    def __init__(
        self,
        clob_client: Any,
        price_source: PriceSource,
        poll_interval_s: float = 0.5,
    ) -> None:
        self.clob_client = clob_client
        self.price_source = price_source
        self.poll_interval_s = poll_interval_s
        self._triggers: dict[str, TriggerSpec] = {}
        self._running = False

    def list_triggers(self) -> list[TriggerSpec]:
        """Return all currently armed triggers."""
        return list(self._triggers.values())

    def remove_trigger(self, token_id: str) -> TriggerSpec | None:
        """Disarm a trigger. Returns the removed spec, or ``None`` if not found."""
        return self._triggers.pop(token_id, None)

    async def run(self) -> None:
        """Run the monitor loop. Cancel via ``stop()`` or task cancellation."""
        raise NotImplementedError("v0.3.0: poll loop, evaluate predicates, dispatch exits")

    def stop(self) -> None:
        """Signal the monitor loop to exit on its next iteration."""
        self._running = False

    @abstractmethod
    async def _evaluate(self, spec: TriggerSpec, current_price: float) -> bool:
        """Return True if ``spec`` should fire at ``current_price``."""

    @abstractmethod
    async def _dispatch_exit(self, spec: TriggerSpec) -> None:
        """Place the market exit order for ``spec``. Subclasses delegate to ``orders.place``."""
