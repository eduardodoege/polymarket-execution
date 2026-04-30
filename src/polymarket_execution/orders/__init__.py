"""Order placement and fill price reconciliation.

Two modules:

- ``place`` — place orders with sane defaults and explicit failure modes.
- ``fills`` — get the **true** average fill price via ``client.get_trades``,
  not the limit price returned by ``get_order_status``. This fixes a
  critical PnL bug — see ``orders.fills`` docstring for the cautionary
  tale.
"""

from polymarket_execution.orders.fills import get_order_avg_fill_price
from polymarket_execution.orders.place import place_market_order

__all__ = ["place_market_order", "get_order_avg_fill_price"]
