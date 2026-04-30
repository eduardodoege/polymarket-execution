"""Polymarket ChainLink RTDS WebSocket price feed.

This is the same feed Polymarket uses to resolve crypto markets via its
ChainLink off-chain signer. Using it eliminates the oracle-drift problem
where a bot's price view (e.g., Coinbase) disagrees with the market's
final resolution, causing wrong-side losses on borderline cycles.

Endpoint: ``wss://ws-live-data.polymarket.com`` (no auth)
Topic: ``crypto_prices_chainlink``
Symbols: ``btc/usd``, ``eth/usd``, ``sol/usd``, ``xrp/usd``
Cadence: ~1 tick/s per symbol
Docs: https://docs.polymarket.com/developers/RTDS/RTDS-crypto-prices

Quirk
-----
Subscribing **with** a symbol filter only returns the historical snapshot
(~60s) and fails to register live updates due to a server-side bug.

Workaround:

- For **live updates**: subscribe without filter, filter client-side by
  ``payload.symbol``.
- For **historical lookup** (e.g., resolving a "price-to-beat" anchor):
  subscribe with the filter, take the snapshot, close the connection.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from polymarket_execution.price_feed.base import PriceFeed


class ChainLinkRTDSFeed(PriceFeed):
    """ChainLink-aligned WebSocket price feed via Polymarket RTDS."""

    def __init__(self, url: str | None = None) -> None:
        from polymarket_execution.constants import CHAINLINK_RTDS_WS_URL

        self.url = url or CHAINLINK_RTDS_WS_URL
        self._ws = None

    async def connect(self) -> None:
        raise NotImplementedError(
            "v0.3.0: open WS, subscribe to crypto_prices_chainlink without filter"
        )

    async def disconnect(self) -> None:
        raise NotImplementedError("v0.3.0: close WS gracefully")

    def subscribe(self, symbol: str) -> AsyncIterator[float]:
        raise NotImplementedError("v0.3.0: filter inbound messages by payload.symbol == symbol")

    async def last_price(self, symbol: str) -> float | None:
        raise NotImplementedError("v0.3.0: track last observed price per symbol")

    async def fetch_at_time(
        self,
        symbol: str,
        target_ts: float,
        tolerance_s: float = 5.0,
    ) -> float | None:
        raise NotImplementedError(
            "v0.3.0: open temp WS WITH filter (snapshot mode), "
            "find tick closest to target_ts, return None if outside tolerance"
        )
