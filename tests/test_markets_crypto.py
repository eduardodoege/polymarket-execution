"""Tests for ``polymarket_execution.markets.crypto`` (real implementation)."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from polymarket_execution.markets.crypto import (
    BLOCK_DURATIONS_S,
    CryptoMarket,
    CryptoMarketDiscovery,
    discover_current_market,
)

# --- parse_price_to_beat ---


@pytest.mark.parametrize(
    "question, expected",
    [
        ("Will BTC be above $76,500.00 at 3pm UTC?", 76_500.00),
        ("ETH up by 12:30 UTC if price > $3,142.55", 3_142.55),
        ("SOL >$200 by close?", 200.0),
        ("XRP > $2 in 5 min?", 2.0),
        ("Random question with no price", None),
        ("Empty $ sign without digits", None),
    ],
)
def test_parse_price_to_beat(question: str, expected: float | None) -> None:
    assert CryptoMarket.parse_price_to_beat(question) == expected


# --- CryptoMarketDiscovery basics ---


def test_unsupported_window_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported window"):
        CryptoMarketDiscovery(window="2m")


@pytest.mark.parametrize("window, duration", BLOCK_DURATIONS_S.items())
def test_supported_windows(window: str, duration: int) -> None:
    discovery = CryptoMarketDiscovery(window=window)
    assert discovery.duration_s == duration
    discovery.close()


def test_current_block_timestamp_aligns_to_window() -> None:
    discovery = CryptoMarketDiscovery(window="5m")
    ts = discovery.current_block_timestamp()
    assert ts % 300 == 0
    assert ts <= int(time.time())
    discovery.close()


def test_block_end_timestamp() -> None:
    discovery = CryptoMarketDiscovery(window="15m")
    assert discovery.block_end_timestamp(1_777_475_100) == 1_777_475_100 + 900
    discovery.close()


def test_build_slug_uses_lowercase_and_window() -> None:
    discovery = CryptoMarketDiscovery(window="5m")
    assert discovery.build_slug("BTC", 1_777_475_100) == "btc-updown-5m-1777475100"
    assert discovery.build_slug("eth", 1_777_475_100) == "eth-updown-5m-1777475100"
    discovery.close()


def test_build_slug_includes_correct_window() -> None:
    discovery = CryptoMarketDiscovery(window="1h")
    assert discovery.build_slug("btc", 1_777_475_100) == "btc-updown-1h-1777475100"
    discovery.close()


# --- parse_market ---


SAMPLE_GAMMA_RESPONSE = {
    "slug": "btc-updown-5m-1777475100",
    "question": "Will Bitcoin be above $76,500.00 by 5pm UTC?",
    "conditionId": "0xabc",
    "outcomePrices": '["0.62", "0.38"]',
    "clobTokenIds": '["0xtokenYES", "0xtokenNO"]',
}


def test_parse_market_extracts_all_fields() -> None:
    discovery = CryptoMarketDiscovery(window="5m")
    market = discovery.parse_market(SAMPLE_GAMMA_RESPONSE, "btc", 1_777_475_100)
    assert market is not None
    assert market.symbol == "btc"
    assert market.window == "5m"
    assert market.slug == "btc-updown-5m-1777475100"
    assert market.condition_id == "0xabc"
    assert market.yes_price == 0.62
    assert market.no_price == 0.38
    assert market.yes_token_id == "0xtokenYES"
    assert market.no_token_id == "0xtokenNO"
    assert market.price_to_beat == 76_500.00
    assert market.block_start == 1_777_475_100
    assert market.block_end == 1_777_475_400
    discovery.close()


def test_parse_market_handles_dict_outcome_prices() -> None:
    """Gamma sometimes returns lists already parsed (not stringified)."""
    discovery = CryptoMarketDiscovery(window="5m")
    payload = dict(SAMPLE_GAMMA_RESPONSE)
    payload["outcomePrices"] = [0.55, 0.45]  # type: ignore[assignment]
    payload["clobTokenIds"] = ["0xtokYES", "0xtokNO"]  # type: ignore[assignment]
    market = discovery.parse_market(payload, "eth", 1_777_475_100)
    assert market is not None
    assert market.yes_price == 0.55
    assert market.no_price == 0.45
    discovery.close()


def test_parse_market_returns_none_on_malformed_payload() -> None:
    discovery = CryptoMarketDiscovery(window="5m")
    bad = {"outcomePrices": "not-json"}
    assert discovery.parse_market(bad, "btc", 0) is None
    discovery.close()


# --- CryptoMarket properties ---


def _market(block_end_offset_s: int) -> CryptoMarket:
    now = int(time.time())
    return CryptoMarket(
        symbol="btc",
        window="5m",
        slug="btc-updown-5m-x",
        block_start=now - 60,
        block_end=now + block_end_offset_s,
        yes_price=0.55,
        no_price=0.45,
        condition_id="0xabc",
        question="Will BTC be above $1.00?",
        yes_token_id="0xY",
        no_token_id="0xN",
    )


def test_time_remaining_positive() -> None:
    m = _market(block_end_offset_s=120)
    # Allow 1s clock-tick fuzziness
    assert 119 <= m.time_remaining_s <= 120


def test_time_remaining_clamped_to_zero_after_end() -> None:
    m = _market(block_end_offset_s=-10)
    assert m.time_remaining_s == 0
    assert m.minutes_remaining == 0


def test_polymarket_url_uses_slug() -> None:
    m = _market(block_end_offset_s=120)
    assert m.polymarket_url == "https://polymarket.com/event/btc-updown-5m-x"


def test_str_includes_symbol_window_prices() -> None:
    m = _market(block_end_offset_s=120)
    s = str(m)
    assert "BTC" in s
    assert "5m" in s
    assert "0.55" in s
    assert "0.45" in s


# --- fetch_market_raw and discover_market (mocked HTTP) ---


def _mock_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status.return_value = None
    return resp


def test_fetch_market_raw_returns_none_on_404() -> None:
    discovery = CryptoMarketDiscovery(window="5m")
    discovery._client = MagicMock()
    discovery._client.get.return_value = _mock_response(404)
    assert discovery.fetch_market_raw("nonexistent-slug") is None


def test_fetch_market_raw_returns_json_on_200() -> None:
    discovery = CryptoMarketDiscovery(window="5m")
    discovery._client = MagicMock()
    discovery._client.get.return_value = _mock_response(200, SAMPLE_GAMMA_RESPONSE)
    assert discovery.fetch_market_raw("any-slug") == SAMPLE_GAMMA_RESPONSE


def test_discover_market_end_to_end_with_mock() -> None:
    discovery = CryptoMarketDiscovery(window="5m")
    discovery._client = MagicMock()
    discovery._client.get.return_value = _mock_response(200, SAMPLE_GAMMA_RESPONSE)
    market = discovery.discover_market("btc")
    assert market is not None
    assert market.symbol == "btc"
    assert market.condition_id == "0xabc"


def test_discover_markets_skips_404s() -> None:
    discovery = CryptoMarketDiscovery(window="5m")
    discovery._client = MagicMock()
    discovery._client.get.side_effect = [
        _mock_response(200, SAMPLE_GAMMA_RESPONSE),
        _mock_response(404),
        _mock_response(200, SAMPLE_GAMMA_RESPONSE),
    ]
    markets = discovery.discover_markets(["btc", "eth", "sol"])
    assert len(markets) == 2  # eth was 404, skipped


# --- module-level convenience fns ---


def test_discover_current_market_module_fn_uses_context_manager() -> None:
    with patch("polymarket_execution.markets.crypto.CryptoMarketDiscovery") as cls:
        instance = MagicMock()
        instance.discover_market.return_value = "fake_market"
        cls.return_value.__enter__.return_value = instance
        cls.return_value.__exit__.return_value = None
        result = discover_current_market("btc", window="15m")
    assert result == "fake_market"
    cls.assert_called_once_with(
        window="15m",
        gamma_api_url="https://gamma-api.polymarket.com",
        resolve_ptb=True,
    )


# --- resolve_ptb path (ChainLink RTDS fallback) ---


PAYLOAD_WITHOUT_PTB_IN_QUESTION = {
    "slug": "btc-updown-5m-1777596900",
    "question": "Bitcoin Up or Down - April 30, 8:55PM-9:00PM ET",
    "conditionId": "0xabc",
    "outcomePrices": '["0.5", "0.5"]',
    "clobTokenIds": '["0xY", "0xN"]',
}


def test_parse_market_calls_chainlink_when_question_has_no_ptb_and_resolve_enabled() -> None:
    discovery = CryptoMarketDiscovery(window="5m", resolve_ptb=True)
    with patch.object(
        CryptoMarketDiscovery, "_resolve_ptb_via_chainlink", return_value=76_500.42
    ) as mocked:
        market = discovery.parse_market(PAYLOAD_WITHOUT_PTB_IN_QUESTION, "btc", 1_777_596_900)
    assert market is not None
    assert market.price_to_beat == 76_500.42
    mocked.assert_called_once_with("btc", 1_777_596_900)
    discovery.close()


def test_parse_market_skips_chainlink_when_resolve_disabled() -> None:
    discovery = CryptoMarketDiscovery(window="5m", resolve_ptb=False)
    with patch.object(CryptoMarketDiscovery, "_resolve_ptb_via_chainlink") as mocked:
        market = discovery.parse_market(PAYLOAD_WITHOUT_PTB_IN_QUESTION, "btc", 1_777_596_900)
    assert market is not None
    assert market.price_to_beat is None
    mocked.assert_not_called()
    discovery.close()


def test_parse_market_skips_chainlink_when_question_already_has_ptb() -> None:
    """If the question carries the $ value, the regex parser wins — no WS call."""
    discovery = CryptoMarketDiscovery(window="5m", resolve_ptb=True)
    with patch.object(CryptoMarketDiscovery, "_resolve_ptb_via_chainlink") as mocked:
        market = discovery.parse_market(SAMPLE_GAMMA_RESPONSE, "btc", 1_777_475_100)
    assert market is not None
    assert market.price_to_beat == 76_500.0  # from question
    mocked.assert_not_called()
    discovery.close()


def test_resolve_ptb_returns_none_when_called_from_event_loop() -> None:
    """In an async context the helper bails out (with a warning) instead of asyncio.run."""
    import asyncio

    async def _inside_loop() -> float | None:
        discovery = CryptoMarketDiscovery(window="5m", resolve_ptb=True)
        try:
            return discovery._resolve_ptb_via_chainlink("btc", 1_000_000)
        finally:
            discovery.close()

    assert asyncio.run(_inside_loop()) is None


# --- safety: SAMPLE_GAMMA_RESPONSE matches what the real Gamma API returns ---


def test_sample_payload_has_required_fields() -> None:
    """If Polymarket changes the Gamma API shape, this is the canary."""
    required = {"slug", "question", "conditionId", "outcomePrices", "clobTokenIds"}
    assert required.issubset(SAMPLE_GAMMA_RESPONSE.keys())
    # outcomePrices should be JSON-decodable into a list of two floats
    parsed = json.loads(SAMPLE_GAMMA_RESPONSE["outcomePrices"])
    assert len(parsed) == 2
