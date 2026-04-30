"""Price feeds for trigger monitors.

Currently provides one feed implementation: ``ChainLinkRTDSFeed``, which
wraps Polymarket's official ChainLink-aligned WebSocket feed
(``wss://ws-live-data.polymarket.com``). This is the same feed Polymarket
uses to resolve crypto markets, so using it eliminates oracle drift
between your bot's view of price and the market's resolution.
"""

from polymarket_execution.price_feed.base import PriceFeed
from polymarket_execution.price_feed.chainlink_rtds import ChainLinkRTDSFeed

__all__ = ["PriceFeed", "ChainLinkRTDSFeed"]
