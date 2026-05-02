"""Polymarket CLOB v2 WebSocket subscriptions.

Currently exposes the public **market** WebSocket — book updates for one
or more conditional-token IDs. The private **user** WebSocket (auth'd
order/fill events) is not implemented yet; it will land together with
the orders/lifecycle modules.

Endpoint: ``wss://ws-subscriptions-clob.polymarket.com/ws/market`` (no auth)
"""

from polymarket_execution.clob_ws.models import OrderBook, OrderBookLevel
from polymarket_execution.clob_ws.orderbook import OrderBookStream

__all__ = ["OrderBook", "OrderBookLevel", "OrderBookStream"]
