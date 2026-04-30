"""CLI: list and inspect Polymarket markets.

The ``crypto`` subcommand is native (no extra required). The ``list`` and
``show`` subcommands require ``pip install polymarket-execution[markets]``.
"""

from __future__ import annotations

import typer

from polymarket_execution.markets.crypto import (
    BLOCK_DURATIONS_S,
    DEFAULT_SYMBOLS,
    CryptoMarket,
    discover_current_market,
    discover_current_markets,
)

app = typer.Typer(no_args_is_help=True)


@app.command("crypto")
def crypto(
    symbol: str | None = typer.Option(
        None,
        "--symbol",
        "-s",
        help="One symbol (btc, eth, sol, xrp). Omit to fetch all default symbols.",
    ),
    window: str = typer.Option(
        "5m",
        "--window",
        "-w",
        help=f"Time window. One of: {sorted(BLOCK_DURATIONS_S)}.",
    ),
) -> None:
    """Discover the current block's crypto up/down markets (no extra dependency)."""
    if window not in BLOCK_DURATIONS_S:
        raise typer.BadParameter(
            f"Unsupported window {window!r}; pick one of {sorted(BLOCK_DURATIONS_S)}"
        )

    if symbol is not None:
        market = discover_current_market(symbol, window=window)
        if market is None:
            typer.echo(
                f"No market found for {symbol.upper()} {window} (current block not yet listed)"
            )
            raise typer.Exit(code=1)
        _print_market_table([market])
        return

    markets = discover_current_markets(window=window)
    if not markets:
        typer.echo(f"No markets listed yet for window {window} (symbols tried: {DEFAULT_SYMBOLS})")
        raise typer.Exit(code=1)
    _print_market_table(markets)


@app.command("list")
def list_markets(
    active: bool = typer.Option(True, help="Filter to currently active markets."),
    limit: int = typer.Option(50),
) -> None:
    """List markets across categories (requires the ``[markets]`` extra)."""
    raise NotImplementedError("v0.5.0: call markets.general.list_markets, print table")


@app.command("show")
def show_market(condition_id: str = typer.Argument(...)) -> None:
    """Show full metadata for one market by condition_id (requires ``[markets]`` extra)."""
    raise NotImplementedError("v0.5.0: call markets.general.get_market, print details")


def _print_market_table(markets: list[CryptoMarket]) -> None:
    """Render a compact table of CryptoMarket rows."""
    typer.echo(f"{'SYMBOL':<6} {'WIN':<4} {'YES':>5} {'NO':>5} {'REMAIN':>7}  PTB")
    typer.echo("-" * 60)
    for m in markets:
        ptb = f"${m.price_to_beat:,.2f}" if m.price_to_beat is not None else "—"
        typer.echo(
            f"{m.symbol.upper():<6} {m.window:<4} {m.yes_price:>5.2f} {m.no_price:>5.2f} "
            f"{m.minutes_remaining:>5.1f}min  {ptb}"
        )
