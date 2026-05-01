"""Tests for ``polymarket_execution.price_feed.chainlink_rtds``.

Internal helpers (``_extract_snapshot``, ``_closest_to``, ``_extract_live_tick``)
are tested directly. The ``fetch_price_at_time`` and ``fetch_current_price``
classmethods are tested with an AsyncMock WebSocket so no network is touched.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from polymarket_execution.price_feed.chainlink_rtds import (
    DEFAULT_TOLERANCE_S,
    SYMBOL_MAP,
    ChainLinkRTDSFeed,
    _closest_to,
    _decode_message,
    _extract_live_tick,
    _extract_snapshot,
)

# --- _decode_message ---


def test_decode_message_handles_str() -> None:
    assert _decode_message('{"a": 1}') == {"a": 1}


def test_decode_message_handles_bytes() -> None:
    assert _decode_message(b'{"a": 2}') == {"a": 2}


def test_decode_message_returns_none_on_empty() -> None:
    assert _decode_message("") is None
    assert _decode_message("   ") is None


def test_decode_message_returns_none_on_invalid_json() -> None:
    assert _decode_message("not json") is None


def test_decode_message_returns_none_on_non_dict() -> None:
    assert _decode_message("[1, 2, 3]") is None
    assert _decode_message('"a string"') is None


def test_decode_message_returns_none_on_unknown_type() -> None:
    assert _decode_message(12345) is None  # type: ignore[arg-type]


# --- _extract_snapshot ---


def test_extract_snapshot_returns_list_when_present() -> None:
    msg = json.dumps(
        {
            "payload": {
                "data": [
                    {"timestamp": 1000, "value": 100.0},
                    {"timestamp": 2000, "value": 200.0},
                ]
            }
        }
    )
    snapshot = _extract_snapshot(msg)
    assert snapshot is not None
    assert len(snapshot) == 2
    assert snapshot[0]["value"] == 100.0


def test_extract_snapshot_returns_none_without_payload() -> None:
    assert _extract_snapshot('{"topic": "x"}') is None


def test_extract_snapshot_returns_none_without_data_list() -> None:
    assert _extract_snapshot('{"payload": {"data": null}}') is None
    assert _extract_snapshot('{"payload": {"data": []}}') is None
    assert _extract_snapshot('{"payload": {"data": "not a list"}}') is None


def test_extract_snapshot_filters_non_dict_items() -> None:
    msg = json.dumps(
        {
            "payload": {
                "data": [
                    {"timestamp": 1000, "value": 100.0},
                    "garbage",
                    None,
                    {"timestamp": 2000, "value": 200.0},
                ]
            }
        }
    )
    snapshot = _extract_snapshot(msg)
    assert snapshot is not None
    assert len(snapshot) == 2


# --- _extract_live_tick ---


def test_extract_live_tick_returns_value_for_matching_symbol() -> None:
    msg = json.dumps(
        {
            "topic": "crypto_prices_chainlink",
            "payload": {"symbol": "btc/usd", "value": "76500.42"},
        }
    )
    assert _extract_live_tick(msg, "btc/usd") == 76_500.42


def test_extract_live_tick_skips_other_topics() -> None:
    msg = json.dumps(
        {
            "topic": "other_topic",
            "payload": {"symbol": "btc/usd", "value": "1.0"},
        }
    )
    assert _extract_live_tick(msg, "btc/usd") is None


def test_extract_live_tick_skips_other_symbols() -> None:
    msg = json.dumps(
        {
            "topic": "crypto_prices_chainlink",
            "payload": {"symbol": "eth/usd", "value": "3000.0"},
        }
    )
    assert _extract_live_tick(msg, "btc/usd") is None


def test_extract_live_tick_returns_none_on_missing_value() -> None:
    msg = json.dumps({"topic": "crypto_prices_chainlink", "payload": {"symbol": "btc/usd"}})
    assert _extract_live_tick(msg, "btc/usd") is None


def test_extract_live_tick_returns_none_on_unparseable_value() -> None:
    msg = json.dumps(
        {
            "topic": "crypto_prices_chainlink",
            "payload": {"symbol": "btc/usd", "value": "abc"},
        }
    )
    assert _extract_live_tick(msg, "btc/usd") is None


# --- _closest_to ---


def test_closest_to_picks_nearest_tick() -> None:
    snapshot = [
        {"timestamp": 1_000_000, "value": 100.0},  # 1000s
        {"timestamp": 2_000_000, "value": 200.0},  # 2000s
        {"timestamp": 3_000_000, "value": 300.0},  # 3000s
    ]
    # target 2100s -> closest is 2000s (offset 100s, default tolerance 5s -> reject)
    assert _closest_to(snapshot, 2100.0, tolerance_s=5.0) is None
    # target 2002s -> closest is 2000s (offset 2s, tolerance 5s -> ok)
    assert _closest_to(snapshot, 2002.0, tolerance_s=5.0) == 200.0
    # target exactly 3000s -> 300.0
    assert _closest_to(snapshot, 3000.0, tolerance_s=5.0) == 300.0


def test_closest_to_returns_none_on_empty() -> None:
    assert _closest_to([], 1234.0, tolerance_s=5.0) is None


def test_closest_to_skips_malformed_items() -> None:
    snapshot = [
        {"timestamp": "not a number", "value": 1.0},
        {"timestamp": 1000, "value": "garbage"},
        {"value": 5.0},  # missing timestamp
        {"timestamp": 2_000_000, "value": 200.0},
    ]
    assert _closest_to(snapshot, 2000.0, tolerance_s=1.0) == 200.0


def test_closest_to_rejects_outside_tolerance() -> None:
    snapshot = [{"timestamp": 1_000_000, "value": 100.0}]
    assert _closest_to(snapshot, 1000.0, tolerance_s=0.5) == 100.0  # offset 0
    assert _closest_to(snapshot, 1006.0, tolerance_s=5.0) is None  # offset 6s > 5s


# --- ChainLinkRTDSFeed classmethod fetch_price_at_time ---


def _make_ws_with_messages(messages: list[str]) -> AsyncMock:
    """Build an AsyncMock WebSocket whose recv() yields the provided messages."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    ws.recv = AsyncMock(side_effect=messages)
    return ws


@pytest.mark.asyncio
async def test_fetch_price_at_time_returns_value_from_snapshot() -> None:
    target_ts = 1_777_596_900.0
    snapshot_msg = json.dumps(
        {
            "payload": {
                "data": [
                    {"timestamp": int((target_ts - 2) * 1000), "value": 76_500.0},
                    {"timestamp": int(target_ts * 1000), "value": 76_512.42},
                    {"timestamp": int((target_ts + 2) * 1000), "value": 76_520.0},
                ]
            }
        }
    )
    ws = _make_ws_with_messages([snapshot_msg])
    with patch(
        "polymarket_execution.price_feed.chainlink_rtds.websockets.connect",
        new=AsyncMock(return_value=ws),
    ):
        result = await ChainLinkRTDSFeed.fetch_price_at_time("btc", target_ts)
    assert result == 76_512.42
    ws.send.assert_awaited_once()
    ws.close.assert_awaited()


@pytest.mark.asyncio
async def test_fetch_price_at_time_returns_none_for_unsupported_symbol() -> None:
    result = await ChainLinkRTDSFeed.fetch_price_at_time("doge", 1.0)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_price_at_time_returns_none_when_connect_fails() -> None:
    with patch(
        "polymarket_execution.price_feed.chainlink_rtds.websockets.connect",
        new=AsyncMock(side_effect=OSError("connection refused")),
    ):
        result = await ChainLinkRTDSFeed.fetch_price_at_time("btc", 1.0)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_price_at_time_skips_messages_until_snapshot_arrives() -> None:
    target_ts = 1_777_596_900.0
    noise_msg = json.dumps({"topic": "other"})
    snapshot_msg = json.dumps(
        {"payload": {"data": [{"timestamp": int(target_ts * 1000), "value": 42.0}]}}
    )
    ws = _make_ws_with_messages([noise_msg, "{}", "", snapshot_msg])
    with patch(
        "polymarket_execution.price_feed.chainlink_rtds.websockets.connect",
        new=AsyncMock(return_value=ws),
    ):
        result = await ChainLinkRTDSFeed.fetch_price_at_time("btc", target_ts)
    assert result == 42.0


@pytest.mark.asyncio
async def test_fetch_price_at_time_returns_none_when_outside_tolerance() -> None:
    target_ts = 1_777_596_900.0
    snapshot_msg = json.dumps(
        {"payload": {"data": [{"timestamp": int((target_ts - 30) * 1000), "value": 76_500.0}]}}
    )
    ws = _make_ws_with_messages([snapshot_msg])
    with patch(
        "polymarket_execution.price_feed.chainlink_rtds.websockets.connect",
        new=AsyncMock(return_value=ws),
    ):
        result = await ChainLinkRTDSFeed.fetch_price_at_time(
            "btc", target_ts, tolerance_s=DEFAULT_TOLERANCE_S
        )
    assert result is None  # offset 30s > tolerance 5s


# --- ChainLinkRTDSFeed classmethod fetch_current_price ---


@pytest.mark.asyncio
async def test_fetch_current_price_returns_first_matching_tick() -> None:
    other_msg = json.dumps(
        {
            "topic": "crypto_prices_chainlink",
            "payload": {"symbol": "eth/usd", "value": "3000.0"},
        }
    )
    btc_msg = json.dumps(
        {
            "topic": "crypto_prices_chainlink",
            "payload": {"symbol": "btc/usd", "value": "76500.42"},
        }
    )
    ws = _make_ws_with_messages([other_msg, btc_msg])
    with patch(
        "polymarket_execution.price_feed.chainlink_rtds.websockets.connect",
        new=AsyncMock(return_value=ws),
    ):
        result = await ChainLinkRTDSFeed.fetch_current_price("btc")
    assert result == 76_500.42


@pytest.mark.asyncio
async def test_fetch_current_price_returns_none_for_unsupported_symbol() -> None:
    result = await ChainLinkRTDSFeed.fetch_current_price("doge")
    assert result is None


# --- PriceFeed ABC instance methods ---


@pytest.mark.asyncio
async def test_instance_fetch_at_time_delegates_to_classmethod() -> None:
    target_ts = 1_777_596_900.0
    snapshot_msg = json.dumps(
        {"payload": {"data": [{"timestamp": int(target_ts * 1000), "value": 99.99}]}}
    )
    ws = _make_ws_with_messages([snapshot_msg])
    feed = ChainLinkRTDSFeed()
    with patch(
        "polymarket_execution.price_feed.chainlink_rtds.websockets.connect",
        new=AsyncMock(return_value=ws),
    ):
        result = await feed.fetch_at_time("btc", target_ts)
    assert result == 99.99


@pytest.mark.asyncio
async def test_streaming_methods_raise_not_implemented() -> None:
    feed = ChainLinkRTDSFeed()
    with pytest.raises(NotImplementedError, match="v0.3.0"):
        await feed.connect()
    with pytest.raises(NotImplementedError, match="v0.3.0"):
        await feed.disconnect()
    with pytest.raises(NotImplementedError, match="v0.3.0"):
        sub = feed.subscribe("btc")
        assert isinstance(sub, AsyncIterator)  # unreachable
    with pytest.raises(NotImplementedError, match="v0.3.0"):
        await feed.last_price("btc")


# --- SYMBOL_MAP sanity ---


def test_symbol_map_covers_default_crypto_symbols() -> None:
    # Must align with markets.crypto.DEFAULT_SYMBOLS
    for sym in ("btc", "eth", "sol", "xrp"):
        assert sym in SYMBOL_MAP
        assert SYMBOL_MAP[sym].endswith("/usd")
