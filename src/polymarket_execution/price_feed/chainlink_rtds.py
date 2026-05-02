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

This module currently implements the historical one-shot path (used by
``polymarket_execution.markets.crypto`` for PTB resolution) and the
single-tick current-price one-shot. Streaming (``connect`` / ``listen`` /
``subscribe`` / ``last_price``) is not implemented yet -- pending the triggers module.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any, Final

import websockets

from polymarket_execution.constants import (
    CHAINLINK_RTDS_TOPIC,
    CHAINLINK_RTDS_WS_URL,
)
from polymarket_execution.price_feed.base import PriceFeed

SYMBOL_MAP: Final[dict[str, str]] = {
    "btc": "btc/usd",
    "eth": "eth/usd",
    "sol": "sol/usd",
    "xrp": "xrp/usd",
}
"""Lower-case ticker -> RTDS subscription symbol."""

DEFAULT_TOLERANCE_S: Final[float] = 5.0
"""Max acceptable offset between requested target and the closest snapshot tick.

Tightened from the original 15s default so that historical PTB lookups are
indistinguishable from the oracle's own value. In continuous operation the
offset is always 0-5s; if it exceeds this threshold (rare network/RTDS
delay) we return ``None`` so callers fail fast rather than anchor on a
slightly misaligned price.
"""

DEFAULT_TIMEOUT_S: Final[float] = 8.0
"""Wall-clock budget for one historical snapshot fetch (connect + recv)."""

DEFAULT_CURRENT_TIMEOUT_S: Final[float] = 5.0
"""Wall-clock budget for one current-price fetch (first matching live tick)."""


class ChainLinkRTDSFeed(PriceFeed):
    """ChainLink-aligned WebSocket price feed via Polymarket RTDS."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url or CHAINLINK_RTDS_WS_URL

    # --- One-shot lookups (no persistent connection) ---

    @classmethod
    async def fetch_price_at_time(
        cls,
        symbol: str,
        target_ts: float,
        *,
        tolerance_s: float = DEFAULT_TOLERANCE_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        url: str = CHAINLINK_RTDS_WS_URL,
    ) -> float | None:
        """Return the ChainLink value closest to ``target_ts``.

        Opens a one-shot RTDS connection, subscribes with a symbol filter
        (which returns the ~60s historical snapshot in a single message),
        picks the tick closest to ``target_ts``, and closes.

        Returns ``None`` if the symbol is unsupported, the connection
        fails, no snapshot arrives within ``timeout_s``, or the closest
        tick is more than ``tolerance_s`` away from ``target_ts``.
        """
        rtds_symbol = SYMBOL_MAP.get(symbol.lower())
        if rtds_symbol is None:
            return None

        subscribe_msg = json.dumps(
            {
                "action": "subscribe",
                "subscriptions": [
                    {
                        "topic": CHAINLINK_RTDS_TOPIC,
                        "type": "*",
                        "filters": json.dumps({"symbol": rtds_symbol}),
                    }
                ],
            }
        )

        ws = await _connect(url, timeout_s)
        if ws is None:
            return None
        try:
            await ws.send(subscribe_msg)
            return await _read_snapshot_value(ws, target_ts, tolerance_s, timeout_s)
        finally:
            await _safe_close(ws)

    @classmethod
    async def fetch_current_price(
        cls,
        symbol: str,
        *,
        timeout_s: float = DEFAULT_CURRENT_TIMEOUT_S,
        url: str = CHAINLINK_RTDS_WS_URL,
    ) -> float | None:
        """Return the first live ChainLink tick for ``symbol``.

        Opens a one-shot unfiltered subscribe (the filtered path is unusable
        for live updates per the module-level quirk), filters client-side,
        returns the first matching value, and closes.
        """
        rtds_symbol = SYMBOL_MAP.get(symbol.lower())
        if rtds_symbol is None:
            return None

        subscribe_msg = json.dumps(
            {
                "action": "subscribe",
                "subscriptions": [
                    {
                        "topic": CHAINLINK_RTDS_TOPIC,
                        "type": "*",
                    }
                ],
            }
        )

        ws = await _connect(url, timeout_s)
        if ws is None:
            return None
        try:
            await ws.send(subscribe_msg)
            return await _read_first_tick_for_symbol(ws, rtds_symbol, timeout_s)
        finally:
            await _safe_close(ws)

    # --- PriceFeed ABC implementations ---

    async def fetch_at_time(
        self,
        symbol: str,
        target_ts: float,
        tolerance_s: float = DEFAULT_TOLERANCE_S,
    ) -> float | None:
        return await self.fetch_price_at_time(
            symbol, target_ts, tolerance_s=tolerance_s, url=self.url
        )

    # The streaming methods are not implemented yet -- pending the triggers module.

    async def connect(self) -> None:
        raise NotImplementedError(
            "streaming connect is not implemented yet -- pending the triggers "
            "module. Use the fetch_* one-shot classmethods for current use cases."
        )

    async def disconnect(self) -> None:
        raise NotImplementedError(
            "streaming disconnect is not implemented yet -- pending the triggers module."
        )

    def subscribe(self, symbol: str) -> AsyncIterator[float]:
        raise NotImplementedError(
            "streaming subscribe is not implemented yet -- pending the triggers module."
        )

    async def last_price(self, symbol: str) -> float | None:
        raise NotImplementedError(
            "streaming last_price is not implemented yet -- pending the triggers module."
        )


# --- Internal helpers (kept module-private) ---


async def _connect(url: str, timeout_s: float) -> Any | None:
    """Open a WebSocket connection within ``timeout_s``. Returns ``None`` on failure."""
    try:
        return await asyncio.wait_for(
            websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=3,
            ),
            timeout=timeout_s,
        )
    except (TimeoutError, OSError):
        return None


async def _safe_close(ws: Any) -> None:
    """Close a WebSocket without raising."""
    with contextlib.suppress(Exception):
        await ws.close()


async def _read_snapshot_value(
    ws: Any,
    target_ts: float,
    tolerance_s: float,
    timeout_s: float,
) -> float | None:
    """Read messages until a snapshot arrives, return value closest to ``target_ts``."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            return None
        try:
            message = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except TimeoutError:
            return None

        snapshot = _extract_snapshot(message)
        if snapshot is None:
            continue
        return _closest_to(snapshot, target_ts, tolerance_s)


async def _read_first_tick_for_symbol(
    ws: Any,
    rtds_symbol: str,
    timeout_s: float,
) -> float | None:
    """Read messages until a live tick for ``rtds_symbol`` arrives."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            return None
        try:
            message = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except TimeoutError:
            return None

        value = _extract_live_tick(message, rtds_symbol)
        if value is not None:
            return value


def _decode_message(message: object) -> dict[str, Any] | None:
    """Decode a raw WebSocket frame into a dict, or ``None`` if unparseable."""
    if isinstance(message, (bytes, bytearray)):
        try:
            text = message.decode(errors="ignore")
        except Exception:
            return None
    elif isinstance(message, str):
        text = message
    else:
        return None
    if not text.strip():
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _extract_snapshot(message: object) -> list[dict[str, Any]] | None:
    """Return the snapshot list embedded in a message, or ``None`` if absent."""
    data = _decode_message(message)
    if data is None:
        return None
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return None
    snapshot = payload.get("data")
    if not isinstance(snapshot, list) or not snapshot:
        return None
    return [item for item in snapshot if isinstance(item, dict)]


def _extract_live_tick(message: object, rtds_symbol: str) -> float | None:
    """Return the float value from a live tick message that matches ``rtds_symbol``."""
    data = _decode_message(message)
    if data is None or data.get("topic") != CHAINLINK_RTDS_TOPIC:
        return None
    payload = data.get("payload")
    if not isinstance(payload, dict) or payload.get("symbol") != rtds_symbol:
        return None
    value = payload.get("value")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _closest_to(
    snapshot: list[dict[str, Any]],
    target_ts: float,
    tolerance_s: float,
) -> float | None:
    """Return the tick value closest to ``target_ts``, or ``None`` if outside tolerance."""
    best_value: float | None = None
    best_offset: float | None = None
    for item in snapshot:
        ts_ms = item.get("timestamp")
        value = item.get("value")
        if ts_ms is None or value is None:
            continue
        try:
            ts = float(ts_ms) / 1000.0
            val = float(value)
        except (TypeError, ValueError):
            continue
        offset = abs(ts - target_ts)
        if best_offset is None or offset < best_offset:
            best_offset = offset
            best_value = val
    if best_value is None or best_offset is None:
        return None
    if best_offset > tolerance_s:
        return None
    return best_value
