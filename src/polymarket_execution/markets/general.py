"""General market discovery — listing, search, category filtering.

For arbitrary Polymarket markets (politics, sports, entertainment, etc.).
Delegates to ``polymarket-apis`` for paginated listing and filtering.

Requires the ``[markets]`` extra::

    pip install polymarket-execution[markets]

For deterministic crypto up/down market lookup (BTC/ETH/SOL/XRP at
5m/15m/1h windows), use ``polymarket_execution.markets.crypto`` instead —
it does not need this extra and uses one HTTP call per lookup.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MarketSummary:
    """Generic market metadata returned by listing/search calls."""

    condition_id: str
    question: str
    active: bool
    closed: bool
    resolved: bool
    end_date_iso: str | None
    token_ids: tuple[str, ...]


def list_markets(
    *,
    active: bool | None = True,
    closed: bool | None = None,
    limit: int = 100,
) -> list[MarketSummary]:
    """List markets matching the filters. Delegates to ``polymarket-apis``."""
    raise NotImplementedError(
        "v0.5.0: import polymarket_apis (optional [markets] extra), "
        "call its market listing endpoint, map results to MarketSummary"
    )


def find_resolved_markets_for_holder(wallet_address: str) -> list[MarketSummary]:
    """Return resolved markets where ``wallet_address`` holds redeemable shares.

    Used internally by ``redeem.RedeemClient.discover_redeemable``.
    """
    raise NotImplementedError(
        "v0.1.0: query positions endpoint filtered by holder + market.resolved=True"
    )


def get_market(condition_id: str) -> MarketSummary:
    """Fetch full metadata for a single market by ``condition_id``."""
    raise NotImplementedError("v0.5.0: call polymarket-apis market-by-id endpoint")
