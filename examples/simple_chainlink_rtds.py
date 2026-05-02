"""Example: continuously poll the ChainLink RTDS feed for crypto prices.

Every ``RTDS_INTERVAL_S`` seconds (default 10), fetches the latest tick
for BTC/ETH/SOL/XRP via the Polymarket RTDS one-shot WebSocket and
prints them. Same feed Polymarket uses to resolve crypto markets — so
these are the "oracle prices" that decide who wins the market.

Useful as a low-level building block when you need the ChainLink price
itself, separate from the markets.crypto discovery flow (which already
calls this internally to resolve the strike price).

Usage::

    RTDS_INTERVAL_S=10 python examples/simple_chainlink_rtds.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading
from types import FrameType

from polymarket_execution.price_feed.chainlink_rtds import SYMBOL_MAP, ChainLinkRTDSFeed

log = logging.getLogger("simple_chainlink_rtds")


async def _fetch_all(symbols: list[str]) -> dict[str, float | BaseException | None]:
    results = await asyncio.gather(
        *(ChainLinkRTDSFeed.fetch_current_price(sym) for sym in symbols),
        return_exceptions=True,
    )
    return dict(zip(symbols, results, strict=True))


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s"
    )

    interval_s = int(os.environ.get("RTDS_INTERVAL_S", "10"))
    symbols = list(SYMBOL_MAP)  # btc, eth, sol, xrp
    log.info("RTDS loop started, interval=%ds, symbols=%s", interval_s, symbols)

    stop_event = threading.Event()

    def _stop(_signum: int, _frame: FrameType | None) -> None:
        stop_event.set()
        log.info("stop requested; exiting after current iteration")

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while not stop_event.is_set():
        try:
            results = asyncio.run(_fetch_all(symbols))
            for sym, value in results.items():
                if isinstance(value, BaseException):
                    log.warning("%s -> error: %s", sym.upper(), value)
                elif value is None:
                    log.warning("%s -> no tick within timeout", sym.upper())
                else:
                    log.info("%s = $%s", sym.upper(), f"{value:,.2f}")
        except Exception as exc:
            log.error("iteration failed: %s", exc, exc_info=True)

        if stop_event.wait(timeout=interval_s):
            break

    log.info("loop exited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
