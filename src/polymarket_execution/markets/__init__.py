"""Market discovery for Polymarket.

Two modules:

- ``crypto`` — native discovery for Polymarket crypto up/down markets
  (BTC/ETH/SOL/XRP at 5m/15m/1h windows). Uses slug-based lookup against
  the Gamma API; **no SDK dependency**.
- ``general`` — paginated listing, search, and category filtering for
  arbitrary markets (politics, sports, etc.). Requires the ``[markets]``
  extra: ``pip install polymarket-execution[markets]``.

For deterministic crypto lookup, prefer ``crypto`` — it is faster and
doesn't need the extra.
"""

from polymarket_execution.markets.crypto import (
    CryptoMarket,
    CryptoMarketDiscovery,
    discover_current_market,
    discover_current_markets,
)

__all__ = [
    "CryptoMarket",
    "CryptoMarketDiscovery",
    "discover_current_market",
    "discover_current_markets",
]
