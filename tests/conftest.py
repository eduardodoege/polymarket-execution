"""Shared pytest fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest


@dataclass
class FakeOrderBook:
    """Minimal order book for testing price-source helpers."""

    best_bid: float | None = 0.49
    best_ask: float | None = 0.51
    last_trade_price: float | None = 0.50


@pytest.fixture
def fake_book() -> FakeOrderBook:
    return FakeOrderBook()


@pytest.fixture
def empty_book() -> FakeOrderBook:
    return FakeOrderBook(best_bid=None, best_ask=None, last_trade_price=None)


@pytest.fixture
def fake_clob_client() -> MagicMock:
    """A MagicMock standing in for ``py_clob_client_v2.ClobClient``."""
    client = MagicMock(name="FakeClobClient")
    return client
