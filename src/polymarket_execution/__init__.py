"""polymarket-execution — execution utilities for Polymarket CLOB v2.

Battle-tested primitives extracted from a production trading bot:
stop-loss, take-profit, redeem, position reconciliation, order lifecycle,
and recovery layers for masked fills.

This package does not provide trading strategies. It provides the plumbing
that sits between the raw CLOB primitives and your bot's decision loop.
"""

from polymarket_execution._version import __version__

__all__ = ["__version__"]
