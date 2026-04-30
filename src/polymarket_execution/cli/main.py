"""CLI entrypoint — registers all sub-command groups."""

from __future__ import annotations

import typer

from polymarket_execution import __version__
from polymarket_execution.cli import (
    markets as markets_cli,
)
from polymarket_execution.cli import (
    orders as orders_cli,
)
from polymarket_execution.cli import (
    position as position_cli,
)
from polymarket_execution.cli import (
    redeem as redeem_cli,
)
from polymarket_execution.cli import (
    stop_loss as stop_loss_cli,
)
from polymarket_execution.cli import (
    take_profit as take_profit_cli,
)

app = typer.Typer(
    name="polymarket-execution",
    help="Execution utilities for Polymarket CLOB v2 — stop-loss, take-profit, redeem, and more.",
    no_args_is_help=True,
)

app.add_typer(redeem_cli.app, name="redeem", help="Redeem winnings from resolved positions.")
app.add_typer(markets_cli.app, name="markets", help="List and inspect Polymarket markets.")
app.add_typer(stop_loss_cli.app, name="stop-loss", help="Stop-loss monitor and watch commands.")
app.add_typer(take_profit_cli.app, name="take-profit", help="Take-profit monitor commands.")
app.add_typer(orders_cli.app, name="orders", help="Place and inspect orders.")
app.add_typer(position_cli.app, name="position", help="Reconcile CLOB and on-chain positions.")


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(f"polymarket-execution {__version__}")


if __name__ == "__main__":
    app()
