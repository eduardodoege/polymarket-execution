"""Native discovery for Polymarket crypto up/down markets.

Polymarket runs a continuous series of binary "will <symbol> go up or down
by the end of this block" markets at fixed time windows (5 minutes,
15 minutes, 1 hour). Each market is uniquely identified by a deterministic
slug:

    {symbol}-updown-{window}-{block_timestamp}

where ``block_timestamp`` is the Unix epoch rounded down to the nearest
window boundary (``ts - (ts % window_seconds)``).

Because the slug is deterministic, this module looks up the *current*
market for a symbol+window with one HTTP call against the Gamma API —
no need to list all markets and filter, no SDK dependency, no pagination.

Use this when you know what symbol and window you want. For category
search, free-text search, or non-crypto markets, use
``polymarket_execution.markets.general`` (requires the ``[markets]`` extra).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Final

import httpx

BLOCK_DURATIONS_S: Final[dict[str, int]] = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}
"""Window name -> block duration in seconds. Add new windows here as Polymarket adds them."""

DEFAULT_SYMBOLS: Final[tuple[str, ...]] = ("btc", "eth", "sol", "xrp")
"""Crypto symbols Polymarket runs up/down markets for as of 2026-04."""

DEFAULT_GAMMA_API_URL: Final[str] = "https://gamma-api.polymarket.com"


@dataclass
class CryptoMarket:
    """A Polymarket crypto up/down market for a specific symbol and time window."""

    symbol: str
    window: str
    slug: str
    block_start: int
    block_end: int
    yes_price: float
    no_price: float
    condition_id: str
    question: str
    yes_token_id: str
    no_token_id: str
    price_to_beat: float | None = None
    """Strike price extracted from the market question (e.g., $76,500.00)."""

    @staticmethod
    def parse_price_to_beat(question: str) -> float | None:
        """Extract the strike price from a Polymarket up/down question string.

        The question looks like ``"Will BTC be above $76,512.42 on ..."``.
        Returns ``None`` when no dollar amount is found or it can't be parsed.
        """
        match = re.search(r"\$([0-9,]+\.?\d*)", question)
        if match is None:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    @property
    def time_remaining_s(self) -> int:
        """Seconds remaining until the block ends. Zero past the end."""
        return max(0, self.block_end - int(time.time()))

    @property
    def minutes_remaining(self) -> float:
        return self.time_remaining_s / 60

    @property
    def polymarket_url(self) -> str:
        """URL to view this market on polymarket.com."""
        return f"https://polymarket.com/event/{self.slug}"

    def __str__(self) -> str:
        return (
            f"{self.symbol.upper()} {self.window} | "
            f"YES: {self.yes_price:.2f} | NO: {self.no_price:.2f} | "
            f"remaining: {self.minutes_remaining:.1f}min"
        )


class CryptoMarketDiscovery:
    """Discover Polymarket crypto up/down markets via slug-based Gamma API lookup.

    No SDK dependency. The slug pattern is deterministic, so we compute it
    locally and fetch one market at a time.

    Usage::

        with CryptoMarketDiscovery(window="5m") as discovery:
            btc = discovery.discover_market("btc")
            all_active = discovery.discover_markets()  # btc, eth, sol, xrp
    """

    def __init__(
        self,
        window: str = "5m",
        gamma_api_url: str = DEFAULT_GAMMA_API_URL,
        timeout_s: float = 10.0,
    ) -> None:
        if window not in BLOCK_DURATIONS_S:
            supported = sorted(BLOCK_DURATIONS_S)
            raise ValueError(f"Unsupported window {window!r}; must be one of {supported}")
        self.window = window
        self.duration_s = BLOCK_DURATIONS_S[window]
        self.gamma_api_url = gamma_api_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout_s)

    def current_block_timestamp(self) -> int:
        """Unix timestamp of the start of the block currently in progress."""
        now = int(time.time())
        return now - (now % self.duration_s)

    def block_end_timestamp(self, block_start: int) -> int:
        """Unix timestamp of the end of a block that started at ``block_start``."""
        return block_start + self.duration_s

    def build_slug(self, symbol: str, block_timestamp: int) -> str:
        """Build the canonical Polymarket slug for ``symbol`` at ``block_timestamp``."""
        return f"{symbol.lower()}-updown-{self.window}-{block_timestamp}"

    def fetch_market_raw(self, slug: str) -> dict | None:
        """Fetch raw market JSON from the Gamma API. Returns ``None`` on 404."""
        url = f"{self.gamma_api_url}/markets/slug/{slug}"
        response = self._client.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def parse_market(
        self,
        data: dict,
        symbol: str,
        block_start: int,
    ) -> CryptoMarket | None:
        """Parse a Gamma API market response into a ``CryptoMarket``.

        Returns ``None`` when required fields are missing or malformed —
        callers should treat that as "market not yet listed".
        """
        try:
            prices = data.get("outcomePrices", "[0.5, 0.5]")
            if isinstance(prices, str):
                prices = json.loads(prices)
            yes_price = float(prices[0])
            no_price = float(prices[1])

            token_ids = data.get("clobTokenIds", "[]")
            if isinstance(token_ids, str):
                token_ids = json.loads(token_ids)
            yes_token_id = token_ids[0] if len(token_ids) > 0 else ""
            no_token_id = token_ids[1] if len(token_ids) > 1 else ""

            question = data.get("question", "")
            return CryptoMarket(
                symbol=symbol.lower(),
                window=self.window,
                slug=data.get("slug", ""),
                block_start=block_start,
                block_end=self.block_end_timestamp(block_start),
                yes_price=yes_price,
                no_price=no_price,
                condition_id=data.get("conditionId", ""),
                question=question,
                yes_token_id=yes_token_id,
                no_token_id=no_token_id,
                price_to_beat=CryptoMarket.parse_price_to_beat(question),
            )
        except (KeyError, ValueError, IndexError, json.JSONDecodeError):
            return None

    def discover_market(self, symbol: str) -> CryptoMarket | None:
        """Discover the current block's market for one symbol.

        Returns ``None`` if the market for the current block is not yet
        listed on Polymarket (typical at the very start of a new block).
        """
        block_start = self.current_block_timestamp()
        slug = self.build_slug(symbol, block_start)
        data = self.fetch_market_raw(slug)
        if data is None:
            return None
        return self.parse_market(data, symbol, block_start)

    def discover_markets(
        self,
        symbols: tuple[str, ...] | list[str] | None = None,
    ) -> list[CryptoMarket]:
        """Discover the current block's markets for multiple symbols.

        Defaults to ``DEFAULT_SYMBOLS`` (btc, eth, sol, xrp). Markets that
        are not yet listed are silently skipped.
        """
        target_symbols = symbols if symbols is not None else DEFAULT_SYMBOLS
        out: list[CryptoMarket] = []
        for symbol in target_symbols:
            market = self.discover_market(symbol)
            if market is not None:
                out.append(market)
        return out

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> CryptoMarketDiscovery:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def discover_current_market(
    symbol: str,
    window: str = "5m",
    gamma_api_url: str = DEFAULT_GAMMA_API_URL,
) -> CryptoMarket | None:
    """One-shot: discover the current block's market for ``symbol`` at ``window``."""
    with CryptoMarketDiscovery(window=window, gamma_api_url=gamma_api_url) as discovery:
        return discovery.discover_market(symbol)


def discover_current_markets(
    symbols: tuple[str, ...] | list[str] | None = None,
    window: str = "5m",
    gamma_api_url: str = DEFAULT_GAMMA_API_URL,
) -> list[CryptoMarket]:
    """One-shot: discover the current block's markets for multiple symbols at ``window``."""
    with CryptoMarketDiscovery(window=window, gamma_api_url=gamma_api_url) as discovery:
        return discovery.discover_markets(symbols)
