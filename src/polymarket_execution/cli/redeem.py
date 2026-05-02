"""CLI: redeem winnings from resolved positions.

Currently exposes one sub-command: ``auto``. Per-market redemption
(``redeem market <condition_id>``) and dry-run discovery
(``redeem list``) will land together with the higher-level
``RedeemClient`` helpers that back them.
"""

from __future__ import annotations

import logging
import os

import typer

from polymarket_execution.redeem import RedeemClient

app = typer.Typer(no_args_is_help=True)


@app.command("auto")
def auto(
    rpc_url: str | None = typer.Option(
        None,
        "--rpc-url",
        envvar="POLYGON_RPC_URL",
        help=(
            "Polygon RPC endpoint. Omit to fall back to the built-in list of "
            "public Polygon endpoints with automatic retry."
        ),
    ),
    signature_type: int = typer.Option(
        2,
        "--signature-type",
        help="2 = Gnosis Safe (Polymarket default); 0 = EOA-only.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Discover redeemable positions but submit no transactions.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Only print the final summary (suppress per-redeem INFO logs).",
    ),
) -> None:
    """Discover all resolved positions, redeem them, then wrap USDC.e -> pUSD.

    Reads the signing key from the ``POLYMARKET_PRIVATE_KEY`` environment
    variable (never accepted as a CLI argument).
    """
    private_key = os.environ.get("POLYMARKET_PRIVATE_KEY", "").strip()
    if not private_key:
        typer.echo(
            "error: POLYMARKET_PRIVATE_KEY env var is required (the signing EOA private key).",
            err=True,
        )
        raise typer.Exit(code=2)

    logging.basicConfig(
        level=logging.WARNING if quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    with RedeemClient(
        private_key=private_key,
        rpc_url=rpc_url,
        signature_type=signature_type,
    ) as redeemer:
        if dry_run:
            _run_dry_run(redeemer)
            return
        _run_sweep(redeemer)


def _run_dry_run(redeemer: RedeemClient) -> None:
    positions = redeemer.discover_redeemable()
    if not positions:
        typer.echo("nothing redeemable")
        return
    typer.echo(f"would redeem {len(positions)} position(s):")
    for p in positions:
        typer.echo(
            f"  {p.condition_id}  outcome={p.outcome:<3}  shares={p.size:.4f}  value=${p.value:.4f}"
        )


def _run_sweep(redeemer: RedeemClient) -> None:
    result = redeemer.auto_redeem_all()

    if result.redeemed_markets:
        typer.echo(f"redeemed {len(result.redeemed_markets)} market(s):")
        for cid in result.redeemed_markets:
            typer.echo(f"  {cid}")
    else:
        typer.echo("nothing to redeem")

    if result.wrap_tx_hash:
        typer.echo(
            f"wrap: {result.wrap_amount_usdc:.4f} USDC.e -> pUSD (tx={result.wrap_tx_hash[:20]}...)"
        )

    if result.total_gas_used:
        typer.echo(
            f"total gas: {result.total_gas_used:,} units (~{result.total_gas_cost_pol:.6f} POL)"
        )

    if result.failed_markets:
        typer.echo(f"\n{len(result.failed_markets)} failure(s):", err=True)
        for cid, err in result.failed_markets:
            typer.echo(f"  {cid}: {err}", err=True)
        raise typer.Exit(code=1)
