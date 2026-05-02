"""CLI: redeem winnings from resolved positions."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True)


@app.command("auto")
def auto(
    rpc_url: str = typer.Option(..., envvar="POLYGON_RPC_URL", help="Polygon RPC endpoint."),
    safe_address: str | None = typer.Option(
        None,
        envvar="POLYMARKET_SAFE",
        help="Gnosis Safe address (CLOB v2).",
    ),
    dry_run: bool = typer.Option(False, help="Discover but don't submit transactions."),
) -> None:
    """Discover all resolved positions, redeem them, then wrap USDC.e -> pUSD."""
    raise NotImplementedError(
        "redeem auto CLI is not implemented yet -- pending: build RedeemClient, "
        "call auto_redeem_all, print summary"
    )


@app.command("list")
def list_redeemable(
    rpc_url: str = typer.Option(..., envvar="POLYGON_RPC_URL"),
    wallet: str = typer.Option(..., help="Wallet or Safe address to check."),
) -> None:
    """List markets where ``wallet`` has redeemable shares (no transactions sent)."""
    raise NotImplementedError(
        "redeem list CLI is not implemented yet -- pending: call "
        "discover_redeemable, print table of (condition_id, shares, amount)"
    )


@app.command("market")
def market(
    condition_id: str = typer.Argument(..., help="Market condition_id to redeem."),
    rpc_url: str = typer.Option(..., envvar="POLYGON_RPC_URL"),
    safe_address: str | None = typer.Option(None, envvar="POLYMARKET_SAFE"),
) -> None:
    """Redeem one specific market by condition_id."""
    raise NotImplementedError(
        "redeem market CLI is not implemented yet -- pending: build "
        "RedeemClient, call redeem_market, print TX hash"
    )
