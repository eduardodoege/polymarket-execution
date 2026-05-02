"""Tests for the ``redeem`` CLI command (Typer)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from polymarket_execution.cli.main import app
from polymarket_execution.redeem.core import (
    RedeemablePosition,
    RedeemReceipt,
    RedeemResult,
)
from polymarket_execution.redeem.wrap import WrapReceipt

runner = CliRunner()


# --- Test fixtures ---


@pytest.fixture(autouse=True)
def _set_private_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to a valid private key in env so most tests don't need to set one."""
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0x" + "a" * 64)


def _patch_redeem_client():
    """Patch ``RedeemClient`` in the CLI module and return the MagicMock instance."""
    instance = MagicMock(spec=["discover_redeemable", "auto_redeem_all"])
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=instance)
    cm.__exit__ = MagicMock(return_value=None)
    return patch("polymarket_execution.cli.redeem.RedeemClient", return_value=cm), instance


def _result(
    *,
    redeemed: list[str] | None = None,
    failed: list[tuple[str, str]] | None = None,
    wrap_amount: float = 0.0,
    wrap_tx: str | None = None,
    gas_used: int = 0,
    gas_cost: float = 0.0,
) -> RedeemResult:
    wrap_receipt = WrapReceipt(tx_hash=wrap_tx, amount_usdc=wrap_amount) if wrap_tx else None
    return RedeemResult(
        redeemed_markets=redeemed or [],
        failed_markets=failed or [],
        redeem_tx_hashes=[],
        wrap_receipt=wrap_receipt,
        total_gas_used=gas_used,
        total_gas_cost_pol=gas_cost,
    )


# --- Missing key ---


def test_auto_exits_when_private_key_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
    result = runner.invoke(app, ["redeem", "auto"])
    assert result.exit_code == 2
    assert "POLYMARKET_PRIVATE_KEY" in result.output


def test_auto_exits_when_private_key_is_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "   ")
    result = runner.invoke(app, ["redeem", "auto"])
    assert result.exit_code == 2


# --- Dry run ---


def test_dry_run_prints_positions_without_redeeming() -> None:
    patcher, instance = _patch_redeem_client()
    instance.discover_redeemable.return_value = [
        RedeemablePosition(condition_id="0xcond1", size=10.0, value=10.0, outcome="Yes"),
        RedeemablePosition(condition_id="0xcond2", size=5.5, value=5.5, outcome="No"),
    ]
    with patcher:
        result = runner.invoke(app, ["redeem", "auto", "--dry-run"])
    assert result.exit_code == 0
    assert "would redeem 2 position(s)" in result.output
    assert "0xcond1" in result.output
    assert "0xcond2" in result.output
    instance.auto_redeem_all.assert_not_called()


def test_dry_run_with_no_positions_says_so() -> None:
    patcher, instance = _patch_redeem_client()
    instance.discover_redeemable.return_value = []
    with patcher:
        result = runner.invoke(app, ["redeem", "auto", "--dry-run"])
    assert result.exit_code == 0
    assert "nothing redeemable" in result.output


# --- Live sweep (mocked) ---


def test_sweep_with_redeems_and_wrap_prints_summary() -> None:
    patcher, instance = _patch_redeem_client()
    instance.auto_redeem_all.return_value = _result(
        redeemed=["0xcond1", "0xcond2"],
        wrap_amount=12.3456,
        wrap_tx="0xWRAPHASH" + "0" * 60,
        gas_used=291_466,
        gas_cost=0.039,
    )
    with patcher:
        result = runner.invoke(app, ["redeem", "auto"])
    assert result.exit_code == 0
    assert "redeemed 2 market(s)" in result.output
    assert "0xcond1" in result.output
    assert "wrap: 12.3456 USDC.e -> pUSD" in result.output
    assert "291,466 units" in result.output


def test_sweep_with_nothing_says_so() -> None:
    patcher, instance = _patch_redeem_client()
    instance.auto_redeem_all.return_value = _result()
    with patcher:
        result = runner.invoke(app, ["redeem", "auto"])
    assert result.exit_code == 0
    assert "nothing to redeem" in result.output


def test_sweep_with_failures_exits_nonzero_and_lists_them() -> None:
    patcher, instance = _patch_redeem_client()
    instance.auto_redeem_all.return_value = _result(
        redeemed=["0xokay"],
        failed=[("0xbad1", "RPC error: timeout"), ("0xbad2", "nonce conflict")],
    )
    with patcher:
        result = runner.invoke(app, ["redeem", "auto"])
    assert result.exit_code == 1
    assert "redeemed 1 market(s)" in result.output
    assert "2 failure(s)" in result.output
    assert "0xbad1: RPC error: timeout" in result.output
    assert "0xbad2: nonce conflict" in result.output


# --- Flag plumbing ---


def test_auto_passes_rpc_url_and_signature_type_to_client() -> None:
    """The CLI flags should reach RedeemClient's constructor."""
    instance = MagicMock(spec=["discover_redeemable", "auto_redeem_all"])
    instance.auto_redeem_all.return_value = _result()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=instance)
    cm.__exit__ = MagicMock(return_value=None)
    with patch("polymarket_execution.cli.redeem.RedeemClient", return_value=cm) as cls:
        result = runner.invoke(
            app,
            [
                "redeem",
                "auto",
                "--rpc-url",
                "https://polygon-rpc.example",
                "--signature-type",
                "0",
            ],
        )
    assert result.exit_code == 0
    cls.assert_called_once()
    kwargs = cls.call_args.kwargs
    assert kwargs["rpc_url"] == "https://polygon-rpc.example"
    assert kwargs["signature_type"] == 0


def test_rpc_url_falls_back_to_polygon_rpc_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYGON_RPC_URL", "https://from-env.example")
    instance = MagicMock(spec=["discover_redeemable", "auto_redeem_all"])
    instance.auto_redeem_all.return_value = _result()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=instance)
    cm.__exit__ = MagicMock(return_value=None)
    with patch("polymarket_execution.cli.redeem.RedeemClient", return_value=cm) as cls:
        runner.invoke(app, ["redeem", "auto"])
    assert cls.call_args.kwargs["rpc_url"] == "https://from-env.example"


# --- Removed sub-commands ---


def test_list_subcommand_is_not_registered() -> None:
    result = runner.invoke(app, ["redeem", "list"])
    assert result.exit_code != 0


def test_market_subcommand_is_not_registered() -> None:
    result = runner.invoke(app, ["redeem", "market", "0xcond"])
    assert result.exit_code != 0


# --- A live RedeemReceipt to keep the import non-redundant ---


def test_redeem_receipt_minimal_construction() -> None:
    rcpt = RedeemReceipt(condition_id="0xc", success=True, tx_hash="0xtx")
    assert rcpt.condition_id == "0xc"
    assert rcpt.success is True
