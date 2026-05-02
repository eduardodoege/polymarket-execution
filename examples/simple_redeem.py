"""Example: continuously sweep resolved positions and redeem.

Polls the Polymarket Data API every ``REDEEM_INTERVAL_S`` seconds (default
600 = 10 min). When it finds redeemable positions, processes them with
``RedeemClient`` and wraps any USDC.e proceeds to pUSD afterwards. Runs
until Ctrl-C.

Usage::

    POLYMARKET_PRIVATE_KEY=0x... \\
    POLYGON_RPC_URL=https://polygon-rpc.com \\
    REDEEM_INTERVAL_S=600 \\
    python examples/simple_redeem.py
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from types import FrameType

from polymarket_execution.redeem import RedeemClient

log = logging.getLogger("simple_redeem")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s"
    )

    private_key = os.environ["POLYMARKET_PRIVATE_KEY"]
    rpc_url = os.environ.get("POLYGON_RPC_URL")
    interval_s = int(os.environ.get("REDEEM_INTERVAL_S", "600"))

    log.info("redeem loop started, interval=%ds", interval_s)

    stop_event = threading.Event()

    def _stop(_signum: int, _frame: FrameType | None) -> None:
        stop_event.set()
        log.info("stop requested; exiting after current iteration")

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while not stop_event.is_set():
        try:
            with RedeemClient(
                private_key=private_key, rpc_url=rpc_url, signature_type=2
            ) as redeemer:
                result = redeemer.auto_redeem_all()
            if result.redeemed_markets:
                log.info(
                    "redeemed %d market(s); wrap_tx=%s",
                    len(result.redeemed_markets),
                    result.wrap_tx_hash or "n/a",
                )
            else:
                log.info("nothing to redeem")
            if result.failed_markets:
                log.warning(
                    "%d redeem failure(s) this round (will retry next iteration)",
                    len(result.failed_markets),
                )
        except Exception as exc:
            log.error("iteration failed: %s", exc, exc_info=True)

        if stop_event.wait(timeout=interval_s):
            break

    log.info("loop exited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
