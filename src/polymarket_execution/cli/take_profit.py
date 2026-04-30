"""CLI: take-profit monitor commands."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True)


@app.command("watch")
def watch(
    token_id: str = typer.Argument(...),
    entry_price: float = typer.Option(..., help="Entry price (used to compute PnL)."),
    target_pct: float | None = typer.Option(None, help="Target PnL %, e.g. 0.10 for +10%."),
    target_price: float | None = typer.Option(None, help="Absolute target price."),
    size: float = typer.Option(...),
    poll_s: float = typer.Option(0.5),
) -> None:
    """Run a take-profit monitor until the target is reached or Ctrl-C."""
    raise NotImplementedError(
        "v0.3.0: build TakeProfitMonitor, add_take_profit, await monitor.run()"
    )
