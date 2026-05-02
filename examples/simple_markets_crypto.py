"""Example: continuously discover crypto up/down markets at each block boundary.

At every block boundary (5m / 15m / 1h depending on ``CRYPTO_WINDOW``),
fetches the current Polymarket markets for BTC/ETH/SOL/XRP — including
the ChainLink-resolved strike price (PTB) — and prints them. Runs until
Ctrl-C.

Usage::

    CRYPTO_WINDOW=5m python examples/simple_markets_crypto.py
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from types import FrameType

from polymarket_execution.markets import discover_current_markets
from polymarket_execution.markets.crypto import BLOCK_DURATIONS_S

log = logging.getLogger("simple_markets_crypto")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s"
    )

    window = os.environ.get("CRYPTO_WINDOW", "5m")
    if window not in BLOCK_DURATIONS_S:
        log.error("unsupported window %r; pick one of %s", window, sorted(BLOCK_DURATIONS_S))
        return 2

    duration = BLOCK_DURATIONS_S[window]
    log.info("crypto markets loop started, window=%s (%ds)", window, duration)

    stop_event = threading.Event()

    def _stop(_signum: int, _frame: FrameType | None) -> None:
        stop_event.set()
        log.info("stop requested; exiting after current iteration")

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while not stop_event.is_set():
        try:
            markets = discover_current_markets(window=window)
            if not markets:
                log.warning("no markets listed yet for current %s block", window)
            for m in markets:
                ptb = f"${m.price_to_beat:,.2f}" if m.price_to_beat else "?"
                log.info(
                    "%-3s %-3s YES=%.2f NO=%.2f remaining=%4.1fmin PTB=%s",
                    m.symbol.upper(),
                    m.window,
                    m.yes_price,
                    m.no_price,
                    m.minutes_remaining,
                    ptb,
                )
        except Exception as exc:
            log.error("iteration failed: %s", exc, exc_info=True)

        now = int(time.time())
        sleep_for = duration - (now % duration)
        log.info("sleeping %ds until next %s block", sleep_for, window)
        if stop_event.wait(timeout=sleep_for):
            break

    log.info("loop exited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
