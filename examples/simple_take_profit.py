"""Example: monitor a position with take-profit until target hits or Ctrl-C.

Available from v0.3.0.
"""

from __future__ import annotations

import asyncio


async def main() -> None:
    from polymarket_execution.price_reference import use_mid_price
    from polymarket_execution.triggers import TakeProfitMonitor

    monitor = TakeProfitMonitor(clob_client=None, price_source=use_mid_price)
    monitor.add_take_profit(
        token_id="0x...",
        size=100,
        entry_price=0.50,
        target_pnl_pct=0.10,  # exit at +10% PnL
    )
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
