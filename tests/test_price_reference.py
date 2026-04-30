"""Tests for ``polymarket_execution.price_reference`` (real implementation)."""

from __future__ import annotations

import pytest

from polymarket_execution.price_reference import (
    fallback_chain,
    use_best_ask,
    use_best_bid,
    use_last_trade_price,
    use_mid_price,
    with_offset,
)


def test_use_mid_price_returns_average(fake_book):
    assert use_mid_price(fake_book) == pytest.approx(0.50)


def test_use_mid_price_returns_none_when_book_empty(empty_book):
    assert use_mid_price(empty_book) is None


def test_use_best_bid(fake_book, empty_book):
    assert use_best_bid(fake_book) == 0.49
    assert use_best_bid(empty_book) is None


def test_use_best_ask(fake_book, empty_book):
    assert use_best_ask(fake_book) == 0.51
    assert use_best_ask(empty_book) is None


def test_use_last_trade_price(fake_book, empty_book):
    assert use_last_trade_price(fake_book) == 0.50
    assert use_last_trade_price(empty_book) is None


def test_with_offset_adds_to_base_price(fake_book):
    shifted = with_offset(use_mid_price, 0.01)
    assert shifted(fake_book) == pytest.approx(0.51)


def test_with_offset_propagates_none(empty_book):
    shifted = with_offset(use_mid_price, 0.01)
    assert shifted(empty_book) is None


def test_fallback_chain_uses_first_non_none(fake_book, empty_book):
    chain = fallback_chain(use_mid_price, use_last_trade_price)
    assert chain(fake_book) == pytest.approx(0.50)
    # Empty book — both sources return None
    assert chain(empty_book) is None


def test_fallback_chain_skips_none_to_next_source():
    class HalfBook:
        best_bid = None
        best_ask = None
        last_trade_price = 0.42

    chain = fallback_chain(use_mid_price, use_last_trade_price)
    assert chain(HalfBook()) == 0.42  # type: ignore[arg-type]
