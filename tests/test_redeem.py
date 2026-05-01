"""Tests for ``polymarket_execution.redeem`` (real implementation)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from polymarket_execution.exceptions import RedeemError, WrapError
from polymarket_execution.redeem import (
    RedeemablePosition,
    RedeemClient,
    RedeemReceipt,
    RedeemResult,
    SafeRedeemAdapter,
    WrapReceipt,
    wrap_usdce_to_pusd,
)

# --- RedeemablePosition.from_data_api ---


def test_position_from_data_api_camelcase():
    payload = {
        "conditionId": "0xabc",
        "size": "11.5",
        "currentValue": "11.5",
        "outcome": "YES",
    }
    pos = RedeemablePosition.from_data_api(payload)
    assert pos.condition_id == "0xabc"
    assert pos.size == 11.5
    assert pos.value == 11.5
    assert pos.outcome == "YES"


def test_position_from_data_api_snake_case_fallback():
    payload = {
        "condition_id": "0xdef",
        "size": 5.0,
        "value": 5.0,
        "outcome": "NO",
    }
    pos = RedeemablePosition.from_data_api(payload)
    assert pos.condition_id == "0xdef"
    assert pos.size == 5.0
    assert pos.outcome == "NO"


def test_position_from_data_api_handles_missing_fields():
    pos = RedeemablePosition.from_data_api({})
    assert pos.condition_id == ""
    assert pos.size == 0.0
    assert pos.value == 0.0
    assert pos.outcome == "?"


# --- RedeemReceipt / RedeemResult ---


def test_receipt_defaults():
    r = RedeemReceipt(condition_id="0xabc", success=False)
    assert r.tx_hash is None
    assert r.gas_used == 0
    assert r.gas_cost_pol == 0.0
    assert r.error is None


def test_result_wrap_aliases_with_no_wrap():
    result = RedeemResult()
    assert result.wrap_tx_hash is None
    assert result.wrap_amount_usdc == 0.0


def test_result_wrap_aliases_with_wrap():
    result = RedeemResult(
        wrap_receipt=WrapReceipt(
            tx_hash="0xfff", amount_usdc=11.5, gas_used=131_232, gas_cost_pol=0.0175
        )
    )
    assert result.wrap_tx_hash == "0xfff"
    assert result.wrap_amount_usdc == 11.5


# --- RedeemClient construction ---


def _mock_web3_client(address: str = "0x" + "1" * 40) -> MagicMock:
    """Build a MagicMock standing in for polymarket_apis.PolymarketWeb3Client."""
    client = MagicMock(name="MockPolymarketWeb3Client")
    client.address = address
    return client


def test_client_construction_with_web3_client():
    web3 = _mock_web3_client()
    client = RedeemClient(web3_client=web3)
    assert client.web3_client is web3
    assert client.wallet_address == web3.address


def test_client_construction_requires_either_arg():
    with pytest.raises(ValueError, match="Either private_key or web3_client"):
        RedeemClient()


def test_client_rpc_endpoint_ordering_with_preferred():
    web3 = _mock_web3_client()
    client = RedeemClient(
        web3_client=web3,
        rpc_url="https://my-preferred-rpc.example.com",
    )
    # Preferred RPC must come first; defaults follow without dups.
    assert client._rpc_endpoints[0] == "https://my-preferred-rpc.example.com"
    assert "https://my-preferred-rpc.example.com" not in client._rpc_endpoints[1:]


def test_client_close_is_idempotent_when_http_client_injected():
    web3 = _mock_web3_client()
    http = httpx.Client()
    client = RedeemClient(web3_client=web3, http_client=http)
    client.close()
    # Injected HTTP client must not be closed by RedeemClient
    assert not http.is_closed
    http.close()


# --- discover_redeemable ---


def _make_client_with_positions(positions: list[dict]) -> RedeemClient:
    """Build a RedeemClient whose Data API call returns ``positions``."""
    web3 = _mock_web3_client()
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=positions))
    http = httpx.Client(transport=transport)
    return RedeemClient(web3_client=web3, http_client=http)


def test_discover_redeemable_parses_full_payload():
    payload = [
        {"conditionId": "0xa", "size": 10.0, "currentValue": 10.0, "outcome": "YES"},
        {"conditionId": "0xb", "size": 5.0, "currentValue": 5.0, "outcome": "NO"},
    ]
    client = _make_client_with_positions(payload)
    found = client.discover_redeemable()
    assert [p.condition_id for p in found] == ["0xa", "0xb"]


def test_discover_redeemable_skips_empty_positions():
    payload = [
        {"conditionId": "0xempty", "size": 0, "currentValue": 0, "outcome": "YES"},
        {"conditionId": "0xreal", "size": 5.0, "currentValue": 5.0, "outcome": "YES"},
    ]
    client = _make_client_with_positions(payload)
    found = client.discover_redeemable()
    assert len(found) == 1
    assert found[0].condition_id == "0xreal"


def test_discover_redeemable_skips_already_redeemed_in_session():
    payload = [{"conditionId": "0xa", "size": 5.0, "currentValue": 5.0, "outcome": "YES"}]
    client = _make_client_with_positions(payload)
    client._redeemed_conditions.add("0xa")
    found = client.discover_redeemable()
    assert found == []


def test_discover_redeemable_handles_dict_response_shape():
    """Some API responses wrap the list under a ``positions`` key."""
    payload = {
        "positions": [
            {"conditionId": "0xa", "size": 5.0, "currentValue": 5.0, "outcome": "YES"},
        ]
    }
    client = _make_client_with_positions(payload)
    found = client.discover_redeemable()
    assert len(found) == 1


def test_discover_redeemable_raises_on_http_error():
    web3 = _mock_web3_client()
    transport = httpx.MockTransport(lambda req: httpx.Response(500))
    http = httpx.Client(transport=transport)
    client = RedeemClient(web3_client=web3, http_client=http)
    with pytest.raises(RedeemError, match="Data API request failed"):
        client.discover_redeemable()


# --- redeem_market ---


def _ok_receipt(tx_hash: str = "0xdeadbeef", gas_used: int = 200_000) -> MagicMock:
    """Build a successful tx receipt mock (status=1)."""
    receipt = MagicMock()
    receipt.status = 1
    receipt.transaction_hash = tx_hash
    receipt.gas_used = gas_used
    receipt.effective_gas_price = 30_000_000_000  # 30 gwei
    return receipt


def test_redeem_market_success_path():
    web3 = _mock_web3_client()
    web3.redeem_position.return_value = _ok_receipt()
    client = RedeemClient(web3_client=web3)
    receipt = client.redeem_market("0xabc", yes_shares=10.0, no_shares=0.0)

    assert receipt.success
    assert receipt.tx_hash == "0xdeadbeef"
    assert receipt.gas_used == 200_000
    assert receipt.gas_cost_pol > 0
    assert receipt.error is None
    web3.redeem_position.assert_called_once_with(
        condition_id="0xabc", amounts=[10.0, 0.0], neg_risk=False
    )


def test_redeem_market_prepends_0x_when_missing():
    web3 = _mock_web3_client()
    web3.redeem_position.return_value = _ok_receipt()
    client = RedeemClient(web3_client=web3)
    receipt = client.redeem_market("abc", yes_shares=10.0, no_shares=0.0)
    assert receipt.condition_id == "0xabc"


def test_redeem_market_already_redeemed_returns_success():
    web3 = _mock_web3_client()
    web3.redeem_position.side_effect = Exception("execution reverted: already redeemed")
    client = RedeemClient(web3_client=web3)
    receipt = client.redeem_market("0xabc", yes_shares=10.0, no_shares=0.0)
    assert receipt.success
    assert receipt.error == "already redeemed"


def test_redeem_market_nonce_issue_returns_failure_no_retry():
    web3 = _mock_web3_client()
    web3.redeem_position.side_effect = Exception("nonce too low")
    client = RedeemClient(web3_client=web3)
    receipt = client.redeem_market("0xabc", yes_shares=10.0, no_shares=0.0)
    assert not receipt.success
    assert receipt.error is not None and "nonce" in receipt.error.lower()
    # Nonce errors should not be marked as redeemed (so a future session retries)
    assert "0xabc" not in client._redeemed_conditions


def test_redeem_market_failed_tx_status():
    web3 = _mock_web3_client()
    bad_receipt = MagicMock()
    bad_receipt.status = 0
    web3.redeem_position.return_value = bad_receipt
    client = RedeemClient(web3_client=web3)
    receipt = client.redeem_market("0xabc", yes_shares=10.0, no_shares=0.0)
    assert not receipt.success
    assert receipt.error is not None and "tx status 0" in receipt.error


def test_redeem_market_no_receipt_treated_as_success():
    web3 = _mock_web3_client()
    web3.redeem_position.return_value = None
    client = RedeemClient(web3_client=web3)
    receipt = client.redeem_market("0xabc", yes_shares=10.0, no_shares=0.0)
    assert receipt.success
    assert receipt.tx_hash is None


# --- _split_shares ---


def test_split_shares_yes():
    pos = RedeemablePosition("0x1", size=11.0, value=11.0, outcome="YES")
    assert RedeemClient._split_shares(pos) == (11.0, 0.0)


def test_split_shares_no():
    pos = RedeemablePosition("0x1", size=11.0, value=11.0, outcome="NO")
    assert RedeemClient._split_shares(pos) == (0.0, 11.0)


def test_split_shares_unknown_passes_both():
    pos = RedeemablePosition("0x1", size=11.0, value=11.0, outcome="?")
    assert RedeemClient._split_shares(pos) == (11.0, 11.0)


# --- auto_redeem_all flow ---


def test_auto_redeem_all_no_positions_returns_empty_result():
    web3 = _mock_web3_client()
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=[]))
    http = httpx.Client(transport=transport)
    client = RedeemClient(web3_client=web3, http_client=http)
    result = client.auto_redeem_all(sleep_between_s=0)
    assert result.redeemed_markets == []
    assert result.failed_markets == []
    assert result.wrap_receipt is None


def test_auto_redeem_all_full_flow_two_positions(monkeypatch):
    payload = [
        {"conditionId": "0xa", "size": 10.0, "currentValue": 10.0, "outcome": "YES"},
        {"conditionId": "0xb", "size": 5.0, "currentValue": 5.0, "outcome": "NO"},
    ]
    web3 = _mock_web3_client()
    web3.redeem_position.return_value = _ok_receipt(tx_hash="0xtx")
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    http = httpx.Client(transport=transport)
    client = RedeemClient(web3_client=web3, http_client=http, wrap_after_redeem=False)

    result = client.auto_redeem_all(sleep_between_s=0)
    assert sorted(result.redeemed_markets) == ["0xa", "0xb"]
    assert result.redeem_tx_hashes == ["0xtx", "0xtx"]
    assert result.failed_markets == []
    assert web3.redeem_position.call_count == 2


def test_auto_redeem_all_partial_failure_records_both():
    payload = [
        {"conditionId": "0xgood", "size": 10.0, "currentValue": 10.0, "outcome": "YES"},
        {"conditionId": "0xbad", "size": 5.0, "currentValue": 5.0, "outcome": "NO"},
    ]
    web3 = _mock_web3_client()
    web3.redeem_position.side_effect = [
        _ok_receipt(tx_hash="0xokay"),
        Exception("nonce too low"),
    ]
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    http = httpx.Client(transport=transport)
    client = RedeemClient(web3_client=web3, http_client=http, wrap_after_redeem=False)

    result = client.auto_redeem_all(sleep_between_s=0)
    assert result.redeemed_markets == ["0xgood"]
    assert len(result.failed_markets) == 1
    assert result.failed_markets[0][0] == "0xbad"


# --- wrap_usdce_to_pusd ---


def _mock_web3_for_wrap(balance_wei: int) -> MagicMock:
    """Build a web3_client mock with USDC.e balance == balance_wei."""
    client = MagicMock(name="MockPolymarketWeb3Client")
    client.address = "0x" + "1" * 40
    client.usdc_abi = []  # placeholder; not introspected by the wrap path

    usdce_contract = MagicMock()
    usdce_contract.functions.balanceOf.return_value.call.return_value = balance_wei

    onramp_contract = MagicMock()
    onramp_contract.encode_abi.return_value = b"calldata"

    # eth.contract returns either contract based on the address arg
    def contract_factory(address: str, abi):  # noqa: ANN001
        from web3 import Web3

        from polymarket_execution.constants import COLLATERAL_ONRAMP_ADDRESS, USDCE_ADDRESS

        if address == Web3.to_checksum_address(USDCE_ADDRESS):
            return usdce_contract
        if address == Web3.to_checksum_address(COLLATERAL_ONRAMP_ADDRESS):
            return onramp_contract
        raise AssertionError(f"unexpected contract address: {address}")

    client.w3.eth.contract.side_effect = contract_factory
    return client


def test_wrap_returns_none_when_balance_is_zero():
    web3 = _mock_web3_for_wrap(balance_wei=0)
    result = wrap_usdce_to_pusd(web3)
    assert result is None
    web3._execute.assert_not_called()


def test_wrap_success_returns_receipt_with_tx_hash_and_gas():
    web3 = _mock_web3_for_wrap(balance_wei=11_500_000)  # 11.5 USDC.e
    receipt = MagicMock()
    receipt.status = 1
    receipt.transaction_hash = "0xwrap"
    receipt.gas_used = 131_232
    receipt.effective_gas_price = 30_000_000_000
    web3._execute.return_value = receipt

    result = wrap_usdce_to_pusd(web3)
    assert result is not None
    assert result.tx_hash == "0xwrap"
    assert result.amount_usdc == 11.5
    assert result.gas_used == 131_232
    assert result.gas_cost_pol > 0


def test_wrap_raises_on_failed_tx_status():
    web3 = _mock_web3_for_wrap(balance_wei=11_500_000)
    bad_receipt = MagicMock()
    bad_receipt.status = 0
    web3._execute.return_value = bad_receipt
    with pytest.raises(WrapError, match="status=0"):
        wrap_usdce_to_pusd(web3)


def test_wrap_raises_on_no_receipt():
    web3 = _mock_web3_for_wrap(balance_wei=11_500_000)
    web3._execute.return_value = None
    with pytest.raises(WrapError, match="no receipt"):
        wrap_usdce_to_pusd(web3)


# --- SafeRedeemAdapter ---


def test_safe_adapter_safe_address_matches_web3_address():
    web3 = _mock_web3_client(address="0x" + "a" * 40)
    adapter = SafeRedeemAdapter(web3_client=web3)
    assert adapter.safe_address == "0x" + "a" * 40


def test_safe_adapter_is_owner_not_yet_implemented():
    adapter = SafeRedeemAdapter(web3_client=_mock_web3_client())
    with pytest.raises(NotImplementedError):
        adapter.is_owner()


def test_safe_adapter_threshold_not_yet_implemented():
    adapter = SafeRedeemAdapter(web3_client=_mock_web3_client())
    with pytest.raises(NotImplementedError):
        adapter.threshold()
