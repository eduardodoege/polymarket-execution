"""CLI: stop-loss monitor and watch commands."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True)


@app.command("watch")
def watch(
    token_id: str = typer.Argument(..., help="Token ID of the position to watch."),
    trigger: float = typer.Option(..., help="Trigger price (decimal, e.g. 0.45)."),
    size: float = typer.Option(..., help="Position size in shares."),
    side: str = typer.Option("long", help="long or short."),
    poll_s: float = typer.Option(0.5, help="Poll interval in seconds."),
) -> None:
    """Run a stop-loss monitor in the foreground until Ctrl-C or trigger fires."""
    raise NotImplementedError("v0.3.0: build StopLossMonitor, add_stop, await monitor.run()")
