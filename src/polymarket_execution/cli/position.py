"""CLI: reconcile CLOB and on-chain positions."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True)


@app.command("reconcile")
def reconcile(
    wallet: str = typer.Option(..., help="Wallet or Safe address."),
    rpc_url: str = typer.Option(..., envvar="POLYGON_RPC_URL"),
    tolerance: float = typer.Option(0.01, help="Share-count tolerance for in_sync."),
) -> None:
    """Print a CLOB-vs-chain drift report for ``wallet``."""
    raise NotImplementedError(
        "v0.2.0: build PositionReconciler, call reconcile, print PositionDrift"
    )
