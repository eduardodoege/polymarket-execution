"""Example: subscribe to one or more orderbooks and print every update.

Subscribes to the comma-separated ``ORDERBOOK_TOKEN_IDS`` env var (or a
default pair) on the public Polymarket CLOB v2 market WebSocket and
prints each ``OrderBook`` snapshot as it arrives. Auto-reconnects on
network hiccups. Runs until Ctrl-C.

Usage::

    ORDERBOOK_TOKEN_IDS=0xtoken_yes,0xtoken_no \\
    python examples/simple_orderbook_stream.py
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import sys
from types import FrameType

from polymarket_execution.clob_ws import OrderBookStream

log = logging.getLogger("simple_orderbook_stream")


async def _run(token_ids: list[str], stop_event: asyncio.Event) -> None:
    async with OrderBookStream() as stream:
        await stream.subscribe(token_ids)
        listen_task = asyncio.create_task(_print_books(stream))
        await stop_event.wait()
        listen_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listen_task


async def _print_books(stream: OrderBookStream) -> None:
    async for book in stream.listen():
        bid = f"${book.best_bid:.4f}" if book.best_bid is not None else "?"
        ask = f"${book.best_ask:.4f}" if book.best_ask is not None else "?"
        spread = f"${book.spread:.4f}" if book.spread is not None else "?"
        log.info(
            "%s... bid=%s ask=%s spread=%s (%d bids / %d asks)",
            book.token_id[:18],
            bid,
            ask,
            spread,
            len(book.bids),
            len(book.asks),
        )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s"
    )

    raw = os.environ.get("ORDERBOOK_TOKEN_IDS", "").strip()
    if not raw:
        log.error(
            "set ORDERBOOK_TOKEN_IDS=<comma-separated token ids> — see "
            "examples/simple_markets_crypto.py for how to discover token ids "
            "via markets.crypto"
        )
        return 2
    token_ids = [t.strip() for t in raw.split(",") if t.strip()]
    log.info("orderbook stream starting; subscribing to %d token(s)", len(token_ids))

    loop = asyncio.new_event_loop()
    stop_event = asyncio.Event()

    def _stop(_signum: int, _frame: FrameType | None) -> None:
        log.info("stop requested")
        loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        loop.run_until_complete(_run(token_ids, stop_event))
    finally:
        loop.close()

    log.info("loop exited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
