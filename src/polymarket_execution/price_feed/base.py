"""Abstract price feed interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class PriceFeed(ABC):
    """Abstract async price feed.

    Implementations stream price updates for a given symbol (e.g., ``btc/usd``).
    """

    @abstractmethod
    async def connect(self) -> None:
        """Open the underlying transport (WebSocket, HTTP poller, etc.)."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the transport gracefully."""

    @abstractmethod
    def subscribe(self, symbol: str) -> AsyncIterator[float]:
        """Yield price updates for ``symbol`` until cancelled."""

    @abstractmethod
    async def last_price(self, symbol: str) -> float | None:
        """Return the most recent observed price for ``symbol``, or ``None``."""

    @abstractmethod
    async def fetch_at_time(
        self,
        symbol: str,
        target_ts: float,
        tolerance_s: float = 5.0,
    ) -> float | None:
        """Look up a historical price near ``target_ts``.

        Returns ``None`` if outside tolerance.
        """
