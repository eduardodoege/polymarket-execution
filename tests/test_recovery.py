"""Tests for ``polymarket_execution.recovery``.

Layers 1, 2, and 4 are implemented (pure functions). Layers 3 and 5
require live ClobClient calls and are tested via mocks once implemented.
"""

from __future__ import annotations

from polymarket_execution.recovery import (
    recover_from_matched_orders_error,
    recover_from_network_error,
    recover_from_status_timeout,
)

# --- Layer 1: network error ---


def test_network_recovery_detects_filled_order():
    result = recover_from_network_error(pre_balance=100.0, post_balance=10.0, attempted_qty=90.0)
    assert result.recovered is True
    assert result.matched_size == 90.0
    assert result.detected_via == "network"


def test_network_recovery_ignores_small_drop():
    result = recover_from_network_error(pre_balance=100.0, post_balance=98.0, attempted_qty=90.0)
    assert result.recovered is False
    assert result.matched_size is None


# --- Layer 2: status timeout ---


def test_status_timeout_recovery_detects_filled():
    result = recover_from_status_timeout(pre_balance=50.0, post_balance=4.0, remaining_qty=46.0)
    assert result.recovered is True
    assert result.detected_via == "status_timeout"


def test_status_timeout_recovery_ignores_partial():
    result = recover_from_status_timeout(pre_balance=50.0, post_balance=40.0, remaining_qty=46.0)
    assert result.recovered is False


# --- Layer 4: matched-orders error parsing ---


def test_matched_orders_recovery_parses_error_message():
    msg = "balance: 11012090, sum of matched orders: 11000000"
    # 11_000_000 wei (6-decimal) = 11.0 shares; attempted ~11.24
    result = recover_from_matched_orders_error(error_message=msg, attempted_qty=11.24)
    assert result.recovered is True
    assert result.matched_size == 11.0
    assert result.detected_via == "matched_orders"


def test_matched_orders_recovery_returns_false_when_below_ratio():
    msg = "balance: X, sum of matched orders: 5000000"  # 5.0 shares
    result = recover_from_matched_orders_error(error_message=msg, attempted_qty=11.24)
    assert result.recovered is False


def test_matched_orders_recovery_handles_missing_pattern():
    result = recover_from_matched_orders_error(error_message="random error", attempted_qty=10.0)
    assert result.recovered is False


def test_matched_orders_recovery_is_case_insensitive():
    msg = "Sum Of Matched Orders: 9500000"  # 9.5 shares
    result = recover_from_matched_orders_error(error_message=msg, attempted_qty=10.0)
    assert result.recovered is True
