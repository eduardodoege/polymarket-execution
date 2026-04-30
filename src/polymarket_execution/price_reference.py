"""Pluggable price reference functions for trigger monitors.

Triggers (stop-loss / take-profit) need to know "what price counts" for
the trigger comparison. Different strategies prefer different references:
mid-price, best-bid, best-ask, or last-trade.

These are exposed as callables so users can pass their own (e.g., TWAP,
oracle price, or anything else) without us having to predict every use case.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class OrderBookSnapshot(Protocol):
    """Minimal order book interface required by the built-in price sources."""

    @property
    def best_bid(self) -> float | None: ...

    @property
    def best_ask(self) -> float | None: ...

    @property
    def last_trade_price(self) -> float | None: ...


PriceSource = Callable[[OrderBookSnapshot], float | None]
"""A function that takes an order book snapshot and returns a reference price."""


def use_mid_price(book: OrderBookSnapshot) -> float | None:
    """Mid-point between best bid and best ask. None if either side is empty."""
    if book.best_bid is None or book.best_ask is None:
        return None
    return (book.best_bid + book.best_ask) / 2.0


def use_best_bid(book: OrderBookSnapshot) -> float | None:
    """Best bid price (most conservative for sells)."""
    return book.best_bid


def use_best_ask(book: OrderBookSnapshot) -> float | None:
    """Best ask price."""
    return book.best_ask


def use_last_trade_price(book: OrderBookSnapshot) -> float | None:
    """Price of the most recent executed trade."""
    return book.last_trade_price


def with_offset(source: PriceSource, offset: float) -> PriceSource:
    """Wrap a price source with a fixed additive offset."""

    def _wrapped(book: OrderBookSnapshot) -> float | None:
        base = source(book)
        return None if base is None else base + offset

    return _wrapped


def fallback_chain(*sources: PriceSource) -> PriceSource:
    """Try each source in order, return the first non-None result."""

    def _wrapped(book: OrderBookSnapshot) -> float | None:
        for source in sources:
            result = source(book)
            if result is not None:
                return result
        return None

    return _wrapped


__all__ = [
    "OrderBookSnapshot",
    "PriceSource",
    "use_mid_price",
    "use_best_bid",
    "use_best_ask",
    "use_last_trade_price",
    "with_offset",
    "fallback_chain",
]


# Silence unused-import warning for Any (kept for forward compat)
_ = Any
