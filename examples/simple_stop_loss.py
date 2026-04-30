"""Example: monitor a position with a stop-loss until trigger or Ctrl-C.

Available from v0.3.0.
"""

from __future__ import annotations

import asyncio


async def main() -> None:
    from polymarket_execution.price_reference import use_mid_price
    from polymarket_execution.triggers import StopLossMonitor

    # Plug in your ClobClient
    monitor = StopLossMonitor(clob_client=None, price_source=use_mid_price)
    monitor.add_stop(
        token_id="0x...",  # the conditional token id you hold
        trigger_price=0.45,  # exit if mid-price falls to/below 0.45
        size=100,  # 100 shares
        side="long",
    )
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
