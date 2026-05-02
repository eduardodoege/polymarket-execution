"""Tests for the ``markets`` CLI commands (Typer)."""

from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from polymarket_execution.cli.main import app
from polymarket_execution.markets.crypto import CryptoMarket

runner = CliRunner()


def _fake_market(symbol: str = "btc", *, with_ptb: bool = True) -> CryptoMarket:
    return CryptoMarket(
        symbol=symbol,
        window="5m",
        slug=f"{symbol}-updown-5m-1700000000",
        block_start=1_700_000_000,
        block_end=1_700_000_300,
        yes_price=0.55,
        no_price=0.45,
        condition_id=f"0x{symbol}cond",
        question="Will it go up?",
        yes_token_id=f"0x{symbol}YES",
        no_token_id=f"0x{symbol}NO",
        price_to_beat=76_500.0 if with_ptb else None,
    )


def test_default_table_omits_token_ids() -> None:
    with patch("polymarket_execution.cli.markets.discover_current_markets") as fn:
        fn.return_value = [_fake_market("btc"), _fake_market("eth")]
        result = runner.invoke(app, ["markets", "crypto"])
    assert result.exit_code == 0
    assert "SYMBOL" in result.output
    assert "BTC" in result.output
    assert "ETH" in result.output
    # No token block by default
    assert "Token IDs:" not in result.output
    assert "0xbtcYES" not in result.output


def test_show_tokens_flag_prints_full_token_block() -> None:
    with patch("polymarket_execution.cli.markets.discover_current_markets") as fn:
        fn.return_value = [_fake_market("btc")]
        result = runner.invoke(app, ["markets", "crypto", "--show-tokens"])
    assert result.exit_code == 0
    assert "Token IDs:" in result.output
    assert "0xbtcYES" in result.output
    assert "0xbtcNO" in result.output


def test_show_tokens_short_flag() -> None:
    with patch("polymarket_execution.cli.markets.discover_current_markets") as fn:
        fn.return_value = [_fake_market("eth")]
        result = runner.invoke(app, ["markets", "crypto", "-t"])
    assert result.exit_code == 0
    assert "0xethYES" in result.output


def test_json_output_is_parseable_array_with_token_ids() -> None:
    with patch("polymarket_execution.cli.markets.discover_current_markets") as fn:
        fn.return_value = [_fake_market("btc"), _fake_market("eth")]
        result = runner.invoke(app, ["markets", "crypto", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    by_symbol = {m["symbol"]: m for m in parsed}
    assert by_symbol["btc"]["yes_token_id"] == "0xbtcYES"
    assert by_symbol["btc"]["no_token_id"] == "0xbtcNO"
    # Derived properties are included
    assert "minutes_remaining" in by_symbol["btc"]
    assert "polymarket_url" in by_symbol["btc"]


def test_json_for_single_symbol() -> None:
    with patch("polymarket_execution.cli.markets.discover_current_market") as fn:
        fn.return_value = _fake_market("sol")
        result = runner.invoke(app, ["markets", "crypto", "--symbol", "sol", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)
    assert parsed[0]["symbol"] == "sol"


def test_unsupported_window_exits_nonzero() -> None:
    result = runner.invoke(app, ["markets", "crypto", "--window", "2m"])
    assert result.exit_code != 0


def test_no_market_for_symbol_exits_nonzero() -> None:
    with patch("polymarket_execution.cli.markets.discover_current_market") as fn:
        fn.return_value = None
        result = runner.invoke(app, ["markets", "crypto", "--symbol", "btc"])
    assert result.exit_code == 1
    assert "No market found" in result.output
