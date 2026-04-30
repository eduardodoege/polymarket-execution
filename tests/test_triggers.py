"""Tests for ``polymarket_execution.triggers``."""

from __future__ import annotations

import pytest

from polymarket_execution.price_reference import use_mid_price
from polymarket_execution.triggers import StopLossMonitor, TakeProfitMonitor


def test_stop_loss_arms_and_lists(fake_clob_client):
    monitor = StopLossMonitor(clob_client=fake_clob_client, price_source=use_mid_price)
    monitor.add_stop(token_id="0xabc", trigger_price=0.45, size=100)
    triggers = monitor.list_triggers()
    assert len(triggers) == 1
    assert triggers[0].trigger_price == 0.45  # type: ignore[attr-defined]


def test_stop_loss_remove(fake_clob_client):
    monitor = StopLossMonitor(clob_client=fake_clob_client, price_source=use_mid_price)
    monitor.add_stop(token_id="0xabc", trigger_price=0.45, size=100)
    removed = monitor.remove_trigger("0xabc")
    assert removed is not None
    assert monitor.list_triggers() == []


def test_take_profit_requires_exactly_one_target(fake_clob_client):
    monitor = TakeProfitMonitor(clob_client=fake_clob_client, price_source=use_mid_price)
    # Both omitted
    with pytest.raises(ValueError):
        monitor.add_take_profit(token_id="0x1", size=10, entry_price=0.50)
    # Both provided
    with pytest.raises(ValueError):
        monitor.add_take_profit(
            token_id="0x1", size=10, entry_price=0.50, target_pnl_pct=0.10, target_price=0.60
        )


def test_take_profit_arms_pct_target(fake_clob_client):
    monitor = TakeProfitMonitor(clob_client=fake_clob_client, price_source=use_mid_price)
    spec = monitor.add_take_profit(token_id="0x1", size=10, entry_price=0.50, target_pnl_pct=0.10)
    assert spec.target_pnl_pct == 0.10
    assert spec.target_price is None


def test_take_profit_arms_price_target(fake_clob_client):
    monitor = TakeProfitMonitor(clob_client=fake_clob_client, price_source=use_mid_price)
    spec = monitor.add_take_profit(token_id="0x1", size=10, entry_price=0.50, target_price=0.60)
    assert spec.target_price == 0.60
    assert spec.target_pnl_pct is None
