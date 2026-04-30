"""CLI: place and inspect orders."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True)


@app.command("place")
def place(
    token_id: str = typer.Argument(...),
    side: str = typer.Option(..., help="BUY or SELL."),
    size: float = typer.Option(...),
    price: float | None = typer.Option(None, help="Limit price. Omit for market order."),
    slippage: float = typer.Option(0.05, help="Max slippage for market orders (default 5%)."),
) -> None:
    """Place a single order (market by default, limit if --price is given)."""
    raise NotImplementedError(
        "v0.4.0: dispatch to orders.place.place_market_order or place_limit_order"
    )


@app.command("fill-price")
def fill_price(order_id: str = typer.Argument(...)) -> None:
    """Print the true VWAP fill price for an order via ``get_trades``."""
    raise NotImplementedError("v0.2.0: call orders.fills.get_order_avg_fill_price, print result")
