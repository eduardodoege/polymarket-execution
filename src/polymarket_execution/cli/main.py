"""CLI entrypoint — registers all sub-command groups.

New sub-commands ship together with the feature they expose; we don't
register skeletons here. See `docs/cli.md` for the current command list
and `feedback_examples_cli_policy.md` for the policy.
"""

from __future__ import annotations

import typer

from polymarket_execution import __version__
from polymarket_execution.cli import (
    markets as markets_cli,
)
from polymarket_execution.cli import (
    redeem as redeem_cli,
)

app = typer.Typer(
    name="polymarket-execution",
    help="Execution utilities for Polymarket CLOB v2.",
    no_args_is_help=True,
)

app.add_typer(redeem_cli.app, name="redeem", help="Redeem winnings from resolved positions.")
app.add_typer(markets_cli.app, name="markets", help="Discover Polymarket markets.")


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(f"polymarket-execution {__version__}")


if __name__ == "__main__":
    app()
