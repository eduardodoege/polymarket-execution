"""Tests for ``polymarket_execution.redeem`` (placeholders for v0.1.0 implementation)."""

from __future__ import annotations

import pytest

from polymarket_execution.redeem import RedeemClient, RedeemResult


def test_redeem_result_defaults_are_empty():
    result = RedeemResult()
    assert result.redeemed_markets == []
    assert result.failed_markets == []
    assert result.redeem_tx_hashes == []
    assert result.wrap_tx_hash is None
    assert result.wrap_amount_usdc == 0.0


def test_redeem_client_construction(fake_clob_client):
    client = RedeemClient(
        clob_client=fake_clob_client,
        web3_rpc_url="https://polygon-rpc.com",
        safe_address="0x" + "0" * 40,
    )
    assert client.clob_client is fake_clob_client
    assert client.safe_address == "0x" + "0" * 40


def test_discover_redeemable_not_yet_implemented(fake_clob_client):
    client = RedeemClient(clob_client=fake_clob_client, web3_rpc_url="x")
    with pytest.raises(NotImplementedError):
        client.discover_redeemable()


def test_auto_redeem_all_not_yet_implemented(fake_clob_client):
    client = RedeemClient(clob_client=fake_clob_client, web3_rpc_url="x")
    with pytest.raises(NotImplementedError):
        client.auto_redeem_all()
