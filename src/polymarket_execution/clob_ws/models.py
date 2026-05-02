"""Order book data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OrderBookLevel:
    """A single price level: ``size`` shares offered at ``price``."""

    price: float
    size: float


@dataclass
class OrderBook:
    """Snapshot of the order book for a single conditional-token ID.

    Bids are sorted descending by price (best bid first); asks ascending
    (best ask first). The Polymarket market WebSocket sends a full book
    snapshot per update, so each instance reflects the complete state at
    ``timestamp`` — no incremental application required.
    """

    token_id: str
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)
    timestamp: float = 0.0

    @property
    def best_bid(self) -> float | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> float | None:
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread(self) -> float | None:
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None
