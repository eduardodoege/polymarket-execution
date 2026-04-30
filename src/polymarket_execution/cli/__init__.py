"""Command-line interface for polymarket-execution.

A thin Typer-based CLI over the library modules. Useful for ops tasks
(redeem all, list markets, watch a stop-loss) without writing a script.

Entry point: ``polymarket-execution --help`` (registered via ``[project.scripts]``).
"""

from polymarket_execution.cli.main import app

__all__ = ["app"]
