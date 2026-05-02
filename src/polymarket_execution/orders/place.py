"""Order placement primitives — place market and limit orders with sane defaults."""

from __future__ import annotations

from typing import Any, Literal


def place_market_order(
    clob_client: Any,
    token_id: str,
    side: Literal["BUY", "SELL"],
    size: float,
    *,
    slippage_pct: float = 0.05,
) -> Any:
    """Place a market order with bounded slippage.

    Polymarket has no true market order — this function builds an aggressive
    limit at the best opposite-side price ± ``slippage_pct``.

    Returns the raw order response from ``client.create_and_post_order``.
    Raises ``OrderPlacementError`` on failure.
    """
    raise NotImplementedError(
        "place_market_order is not implemented yet -- pending: read book top, "
        "build aggressive limit at best ± slippage, call create_and_post_order "
        "with order_type=GTC or FOK"
    )


def place_limit_order(
    clob_client: Any,
    token_id: str,
    side: Literal["BUY", "SELL"],
    size: float,
    price: float,
    *,
    order_type: Literal["GTC", "GTD", "FOK"] = "GTC",
) -> Any:
    """Place a limit order at the specified price."""
    raise NotImplementedError(
        "place_limit_order is not implemented yet -- pending: build "
        "OrderArgs(token_id, price, size, side), call create_and_post_order"
    )
