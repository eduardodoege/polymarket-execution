"""CLI: discover Polymarket markets.

Currently exposes only `crypto` (slug-based crypto up/down market
lookup). General listing/search via `polymarket-apis` is not implemented
yet; it will land here together with its implementation.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

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
    no_ptb: bool = typer.Option(
        False,
        "--no-ptb",
        help=(
            "Skip the ChainLink RTDS lookup that resolves the strike price (PTB). "
            "Faster (no WebSocket), but the PTB column will be empty."
        ),
    ),
    show_tokens: bool = typer.Option(
        False,
        "--show-tokens",
        "-t",
        help="Print the full YES/NO conditional-token IDs below the table.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of the human-readable table.",
    ),
) -> None:
    """Discover the current block's crypto up/down markets."""
    if window not in BLOCK_DURATIONS_S:
        raise typer.BadParameter(
            f"Unsupported window {window!r}; pick one of {sorted(BLOCK_DURATIONS_S)}"
        )

    resolve_ptb = not no_ptb

    if symbol is not None:
        market = discover_current_market(symbol, window=window, resolve_ptb=resolve_ptb)
        if market is None:
            typer.echo(
                f"No market found for {symbol.upper()} {window} (current block not yet listed)"
            )
            raise typer.Exit(code=1)
        markets = [market]
    else:
        markets = discover_current_markets(window=window, resolve_ptb=resolve_ptb)
        if not markets:
            typer.echo(
                f"No markets listed yet for window {window} (symbols tried: {DEFAULT_SYMBOLS})"
            )
            raise typer.Exit(code=1)

    if as_json:
        _print_markets_json(markets)
        return

    _print_market_table(markets)
    if show_tokens:
        _print_token_ids(markets)


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


def _print_token_ids(markets: list[CryptoMarket]) -> None:
    """Print the full YES/NO conditional-token IDs below the table."""
    typer.echo("")
    typer.echo("Token IDs:")
    for m in markets:
        sym = m.symbol.upper()
        typer.echo(f"  {sym:<3} YES  {m.yes_token_id}")
        typer.echo(f"  {sym:<3} NO   {m.no_token_id}")


def _print_markets_json(markets: list[CryptoMarket]) -> None:
    """Emit the discovered markets as a JSON array (parseable by jq)."""
    payload = [_market_to_dict(m) for m in markets]
    typer.echo(json.dumps(payload, indent=2))


def _market_to_dict(m: CryptoMarket) -> dict[str, Any]:
    """Serialize a CryptoMarket including derived properties."""
    out: dict[str, Any] = asdict(m)
    out["time_remaining_s"] = m.time_remaining_s
    out["minutes_remaining"] = m.minutes_remaining
    out["polymarket_url"] = m.polymarket_url
    return out
