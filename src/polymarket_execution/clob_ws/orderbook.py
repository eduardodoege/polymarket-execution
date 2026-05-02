"""Polymarket CLOB v2 orderbook WebSocket stream.

Subscribes to the public market WebSocket and yields ``OrderBook``
snapshots as they arrive. Each message from Polymarket carries the full
book for one token, so the consumer never has to apply incremental
updates.

Endpoint: ``wss://ws-subscriptions-clob.polymarket.com/ws/market`` (no auth)
Channel: ``book``

Design notes
------------
- **Auto-reconnect** with exponential backoff (``reconnect_min_delay_s``
  to ``reconnect_max_delay_s``); the resubscribe message is replayed for
  every token tracked in ``self._token_ids``.
- **Data-flow watchdog** instead of WebSocket ping/pong. Some hosting
  proxies (notably SOCKS5 setups) interfere with WS control frames, so
  rather than rely on those, we treat ``no_data_timeout_s`` of silence
  as a dead connection and force a reconnect.
- **Async-iterator API**. Iterate ``stream.listen()`` to receive each
  ``OrderBook`` update; mirror state for whatever consumer needs it.

Example::

    async with OrderBookStream() as stream:
        await stream.subscribe(["0xtoken_yes", "0xtoken_no"])
        async for book in stream.listen():
            print(book.token_id, book.best_bid, book.best_ask)

To compose with other async work (e.g., a price feed), drive
``listen()`` in a task and read from the cached state via
``stream.get_orderbook(token_id)`` from elsewhere.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import AsyncIterator, Iterable
from typing import Any, Final

import websockets
from websockets.exceptions import ConnectionClosed

from polymarket_execution.clob_ws.models import OrderBook, OrderBookLevel

DEFAULT_WS_URL: Final[str] = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DEFAULT_RECONNECT_MIN_DELAY_S: Final[float] = 0.5
DEFAULT_RECONNECT_MAX_DELAY_S: Final[float] = 30.0
DEFAULT_NO_DATA_TIMEOUT_S: Final[float] = 45.0
DEFAULT_RECV_TIMEOUT_S: Final[float] = 5.0
DEFAULT_CONNECT_TIMEOUT_S: Final[float] = 30.0
DEFAULT_MAX_CONNECT_RETRIES: Final[int] = 5

logger = logging.getLogger(__name__)


class OrderBookStream:
    """Async stream of ``OrderBook`` snapshots for one or more tokens."""

    def __init__(
        self,
        *,
        url: str = DEFAULT_WS_URL,
        reconnect_min_delay_s: float = DEFAULT_RECONNECT_MIN_DELAY_S,
        reconnect_max_delay_s: float = DEFAULT_RECONNECT_MAX_DELAY_S,
        no_data_timeout_s: float = DEFAULT_NO_DATA_TIMEOUT_S,
        recv_timeout_s: float = DEFAULT_RECV_TIMEOUT_S,
        connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S,
        max_connect_retries: int = DEFAULT_MAX_CONNECT_RETRIES,
    ) -> None:
        self.url = url
        self._reconnect_min = reconnect_min_delay_s
        self._reconnect_max = reconnect_max_delay_s
        self._no_data_timeout = no_data_timeout_s
        self._recv_timeout = recv_timeout_s
        self._connect_timeout = connect_timeout_s
        self._max_connect_retries = max_connect_retries

        self._ws: Any = None
        self._running = False
        self._connected = False
        self._reconnect_delay = reconnect_min_delay_s
        self._last_data_time = 0.0

        self._orderbooks: dict[str, OrderBook] = {}
        self._token_ids: set[str] = set()

    # --- Lifecycle ---

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    async def connect(self) -> None:
        """Open the WebSocket. Retries up to ``max_connect_retries`` times."""
        last_exc: Exception | None = None
        for attempt in range(1, self._max_connect_retries + 1):
            try:
                logger.debug(
                    "connecting to %s (attempt %d/%d)",
                    self.url,
                    attempt,
                    self._max_connect_retries,
                )
                self._ws = await asyncio.wait_for(
                    websockets.connect(
                        self.url,
                        ping_interval=None,
                        ping_timeout=None,
                        close_timeout=10,
                        max_size=2**23,
                        compression=None,
                    ),
                    timeout=self._connect_timeout,
                )
                self._running = True
                self._connected = True
                self._reconnect_delay = self._reconnect_min
                self._last_data_time = time.time()
                logger.info("connected to CLOB market WebSocket")
                return
            except (TimeoutError, OSError) as exc:
                last_exc = exc
                logger.warning("connect attempt %d failed: %s", attempt, exc)
                if attempt < self._max_connect_retries:
                    await asyncio.sleep(2)

        self._connected = False
        raise ConnectionError(
            f"could not connect to {self.url} after "
            f"{self._max_connect_retries} attempts; last error: {last_exc}"
        )

    async def disconnect(self) -> None:
        """Close the WebSocket. Safe to call when already closed."""
        self._running = False
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None
        self._connected = False
        logger.info("disconnected from CLOB market WebSocket")

    async def __aenter__(self) -> OrderBookStream:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.disconnect()

    # --- Subscriptions ---

    async def subscribe(self, token_ids: Iterable[str]) -> None:
        """Subscribe to book updates for the given conditional-token IDs."""
        token_list = [t for t in token_ids if t]
        if not token_list:
            return
        if self._ws is None:
            await self.connect()
        message = json.dumps({"type": "subscribe", "channel": "book", "assets_ids": token_list})
        await self._ws.send(message)
        self._token_ids.update(token_list)
        logger.debug("subscribed to %d token(s)", len(token_list))

    # --- Listen loop ---

    async def listen(self) -> AsyncIterator[OrderBook]:
        """Yield every ``OrderBook`` snapshot received until ``disconnect()``.

        Reconnects automatically on transport errors and on
        ``no_data_timeout_s`` of silence. Re-raises ``ConnectionError`` if
        a reconnect cannot succeed.
        """
        if self._ws is None:
            await self.connect()
        self._last_data_time = time.time()

        while self._running:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=self._recv_timeout)
            except TimeoutError:
                silence = time.time() - self._last_data_time
                if silence >= self._no_data_timeout and self._running:
                    logger.warning("no data for %.0fs — reconnecting", silence)
                    await self._reconnect()
                continue
            except ConnectionClosed:
                logger.warning("connection closed; reconnecting")
                if self._running:
                    await self._reconnect()
                continue
            except Exception as exc:
                logger.error("listen error: %s", exc)
                await asyncio.sleep(0.1)
                continue

            self._last_data_time = time.time()
            for book in self._parse_message(raw):
                self._orderbooks[book.token_id] = book
                yield book

    async def _reconnect(self) -> None:
        await asyncio.sleep(self._reconnect_delay)
        try:
            await self.connect()
        except ConnectionError:
            self._reconnect_delay = min(self._reconnect_delay * 2, self._reconnect_max)
            raise
        if self._token_ids:
            await self.subscribe(self._token_ids)

    # --- Parsing ---

    def _parse_message(self, raw: object) -> list[OrderBook]:
        """Decode a raw frame into 0+ ``OrderBook`` snapshots."""
        text = _decode(raw)
        if text is None:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []

        items: list[Any]
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = [data]
        else:
            return []

        out: list[OrderBook] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            book = self._parse_book(item)
            if book is not None:
                out.append(book)
        return out

    def _parse_book(self, data: dict[str, Any]) -> OrderBook | None:
        """Parse a single book message dict into an ``OrderBook``."""
        msg_type = data.get("event_type") or data.get("type")
        if msg_type != "book":
            return None
        token_id = data.get("asset_id")
        if not isinstance(token_id, str) or not token_id:
            return None

        bids = _parse_levels(data.get("bids", []))
        asks = _parse_levels(data.get("asks", []))
        bids.sort(key=lambda lvl: lvl.price, reverse=True)
        asks.sort(key=lambda lvl: lvl.price)

        return OrderBook(
            token_id=token_id,
            bids=bids,
            asks=asks,
            timestamp=time.time(),
        )

    # --- State accessors ---

    def get_orderbook(self, token_id: str) -> OrderBook | None:
        return self._orderbooks.get(token_id)

    def get_best_bid(self, token_id: str) -> float | None:
        book = self._orderbooks.get(token_id)
        return book.best_bid if book else None

    def get_best_ask(self, token_id: str) -> float | None:
        book = self._orderbooks.get(token_id)
        return book.best_ask if book else None

    def get_mid_price(self, token_id: str) -> float | None:
        book = self._orderbooks.get(token_id)
        return book.mid_price if book else None


# --- Module-private helpers ---


def _decode(raw: object) -> str | None:
    if isinstance(raw, (bytes, bytearray)):
        try:
            text = raw.decode(errors="ignore")
        except Exception:
            return None
    elif isinstance(raw, str):
        text = raw
    else:
        return None
    return text if text.strip() else None


def _parse_levels(levels: object) -> list[OrderBookLevel]:
    if not isinstance(levels, list):
        return []
    out: list[OrderBookLevel] = []
    for entry in levels:
        if not isinstance(entry, dict):
            continue
        try:
            price = float(entry["price"])
            size = float(entry["size"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append(OrderBookLevel(price=price, size=size))
    return out
