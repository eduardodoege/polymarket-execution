"""Tests for ``polymarket_execution.clob_ws``.

Internal helpers (``_decode``, ``_parse_levels``) and the parser methods
(``_parse_book``, ``_parse_message``) are tested directly. ``connect``,
``subscribe``, ``listen``, and the reconnect path are tested with an
``AsyncMock`` WebSocket so no network is touched.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from websockets.exceptions import ConnectionClosed

from polymarket_execution.clob_ws.models import OrderBook, OrderBookLevel
from polymarket_execution.clob_ws.orderbook import (
    OrderBookStream,
    _decode,
    _parse_levels,
)

# --- OrderBook properties ---


def test_orderbook_best_bid_and_ask() -> None:
    book = OrderBook(
        token_id="0xtok",
        bids=[OrderBookLevel(0.55, 100), OrderBookLevel(0.54, 200)],
        asks=[OrderBookLevel(0.56, 50), OrderBookLevel(0.57, 75)],
    )
    assert book.best_bid == 0.55
    assert book.best_ask == 0.56
    assert book.mid_price == pytest.approx(0.555)
    assert book.spread == pytest.approx(0.01)


def test_orderbook_empty_returns_none_for_derived() -> None:
    book = OrderBook(token_id="0xtok")
    assert book.best_bid is None
    assert book.best_ask is None
    assert book.mid_price is None
    assert book.spread is None


def test_orderbook_one_sided_returns_none_for_mid_and_spread() -> None:
    bids_only = OrderBook(token_id="0xtok", bids=[OrderBookLevel(0.5, 10)])
    assert bids_only.best_bid == 0.5
    assert bids_only.best_ask is None
    assert bids_only.mid_price is None
    assert bids_only.spread is None


# --- _decode ---


def test_decode_handles_str() -> None:
    assert _decode("hello") == "hello"


def test_decode_handles_bytes() -> None:
    assert _decode(b'{"a": 1}') == '{"a": 1}'


def test_decode_returns_none_on_empty() -> None:
    assert _decode("") is None
    assert _decode("   ") is None
    assert _decode(b"") is None


def test_decode_returns_none_on_unknown_type() -> None:
    assert _decode(12345) is None  # type: ignore[arg-type]


# --- _parse_levels ---


def test_parse_levels_valid() -> None:
    raw = [{"price": "0.55", "size": "100"}, {"price": "0.54", "size": "200"}]
    out = _parse_levels(raw)
    assert out == [OrderBookLevel(0.55, 100.0), OrderBookLevel(0.54, 200.0)]


def test_parse_levels_skips_malformed_entries() -> None:
    raw: list[Any] = [
        {"price": "0.55", "size": "100"},
        {"price": "abc", "size": "1"},  # bad price
        {"price": "0.5"},  # missing size
        "not a dict",
        None,
        {"price": "0.51", "size": "5"},
    ]
    out = _parse_levels(raw)
    assert out == [OrderBookLevel(0.55, 100.0), OrderBookLevel(0.51, 5.0)]


def test_parse_levels_returns_empty_on_non_list() -> None:
    assert _parse_levels(None) == []
    assert _parse_levels("x") == []


# --- _parse_book ---


SAMPLE_BOOK_MSG = {
    "event_type": "book",
    "asset_id": "0xtoken123",
    "bids": [{"price": "0.50", "size": "100"}, {"price": "0.49", "size": "200"}],
    "asks": [{"price": "0.52", "size": "50"}, {"price": "0.53", "size": "75"}],
}


def test_parse_book_returns_orderbook_with_sorted_levels() -> None:
    stream = OrderBookStream()
    book = stream._parse_book(SAMPLE_BOOK_MSG)
    assert book is not None
    assert book.token_id == "0xtoken123"
    # Bids descending
    assert [lvl.price for lvl in book.bids] == [0.50, 0.49]
    # Asks ascending
    assert [lvl.price for lvl in book.asks] == [0.52, 0.53]


def test_parse_book_accepts_unprefixed_type_field() -> None:
    payload = dict(SAMPLE_BOOK_MSG)
    del payload["event_type"]
    payload["type"] = "book"
    stream = OrderBookStream()
    assert stream._parse_book(payload) is not None


def test_parse_book_returns_none_on_wrong_type() -> None:
    payload = dict(SAMPLE_BOOK_MSG)
    payload["event_type"] = "price"
    stream = OrderBookStream()
    assert stream._parse_book(payload) is None


def test_parse_book_returns_none_on_missing_asset_id() -> None:
    payload = dict(SAMPLE_BOOK_MSG)
    del payload["asset_id"]
    stream = OrderBookStream()
    assert stream._parse_book(payload) is None


def test_parse_book_re_sorts_input_levels() -> None:
    payload = dict(SAMPLE_BOOK_MSG)
    payload["bids"] = [{"price": "0.49", "size": "1"}, {"price": "0.50", "size": "1"}]
    payload["asks"] = [{"price": "0.53", "size": "1"}, {"price": "0.52", "size": "1"}]
    stream = OrderBookStream()
    book = stream._parse_book(payload)
    assert book is not None
    assert book.best_bid == 0.50
    assert book.best_ask == 0.52


# --- _parse_message ---


def test_parse_message_handles_single_dict() -> None:
    stream = OrderBookStream()
    out = stream._parse_message(json.dumps(SAMPLE_BOOK_MSG))
    assert len(out) == 1


def test_parse_message_handles_batch_list() -> None:
    stream = OrderBookStream()
    second = dict(SAMPLE_BOOK_MSG)
    second["asset_id"] = "0xother"
    out = stream._parse_message(json.dumps([SAMPLE_BOOK_MSG, second]))
    assert {b.token_id for b in out} == {"0xtoken123", "0xother"}


def test_parse_message_skips_non_book_items() -> None:
    stream = OrderBookStream()
    other = {"event_type": "price", "asset_id": "0xx", "price": "0.5"}
    out = stream._parse_message(json.dumps([SAMPLE_BOOK_MSG, other, "garbage", None]))
    assert len(out) == 1


def test_parse_message_returns_empty_on_invalid_json() -> None:
    stream = OrderBookStream()
    assert stream._parse_message("not json") == []


def test_parse_message_returns_empty_on_empty_frame() -> None:
    stream = OrderBookStream()
    assert stream._parse_message("") == []
    assert stream._parse_message(b"") == []


# --- OrderBookStream connect / disconnect ---


def _make_ws(messages: list[Any] | None = None) -> AsyncMock:
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    if messages is not None:
        ws.recv = AsyncMock(side_effect=messages)
    return ws


@pytest.mark.asyncio
async def test_connect_succeeds_on_first_attempt() -> None:
    ws = _make_ws()
    with patch(
        "polymarket_execution.clob_ws.orderbook.websockets.connect",
        new=AsyncMock(return_value=ws),
    ):
        stream = OrderBookStream(max_connect_retries=1)
        await stream.connect()
    assert stream.is_connected
    await stream.disconnect()
    assert not stream.is_connected


@pytest.mark.asyncio
async def test_connect_retries_then_raises_connection_error() -> None:
    with patch(
        "polymarket_execution.clob_ws.orderbook.websockets.connect",
        new=AsyncMock(side_effect=OSError("nope")),
    ):
        stream = OrderBookStream(max_connect_retries=2)
        with pytest.raises(ConnectionError, match="could not connect"):
            await stream.connect()
    assert not stream.is_connected


@pytest.mark.asyncio
async def test_disconnect_is_idempotent() -> None:
    stream = OrderBookStream()
    await stream.disconnect()
    await stream.disconnect()  # no error


@pytest.mark.asyncio
async def test_async_context_manager_connects_and_disconnects() -> None:
    ws = _make_ws()
    with patch(
        "polymarket_execution.clob_ws.orderbook.websockets.connect",
        new=AsyncMock(return_value=ws),
    ):
        async with OrderBookStream() as stream:
            assert stream.is_connected
        assert not stream.is_connected
    ws.close.assert_awaited()


# --- subscribe ---


@pytest.mark.asyncio
async def test_subscribe_sends_correct_message_and_tracks_tokens() -> None:
    ws = _make_ws()
    with patch(
        "polymarket_execution.clob_ws.orderbook.websockets.connect",
        new=AsyncMock(return_value=ws),
    ):
        stream = OrderBookStream()
        await stream.connect()
        await stream.subscribe(["0xtok1", "0xtok2"])

    ws.send.assert_awaited_once()
    payload = json.loads(ws.send.call_args.args[0])
    assert payload == {
        "type": "subscribe",
        "channel": "book",
        "assets_ids": ["0xtok1", "0xtok2"],
    }
    assert stream._token_ids == {"0xtok1", "0xtok2"}


@pytest.mark.asyncio
async def test_subscribe_with_empty_iterable_is_a_noop() -> None:
    ws = _make_ws()
    with patch(
        "polymarket_execution.clob_ws.orderbook.websockets.connect",
        new=AsyncMock(return_value=ws),
    ):
        stream = OrderBookStream()
        await stream.connect()
        await stream.subscribe([])
    ws.send.assert_not_awaited()
    assert stream._token_ids == set()


# --- listen ---


@pytest.mark.asyncio
async def test_listen_yields_books_and_updates_state() -> None:
    msg = json.dumps(SAMPLE_BOOK_MSG)
    ws = _make_ws([msg, ConnectionClosed(None, None)])
    with patch(
        "polymarket_execution.clob_ws.orderbook.websockets.connect",
        new=AsyncMock(return_value=ws),
    ):
        stream = OrderBookStream(recv_timeout_s=0.1, no_data_timeout_s=0.2)
        await stream.connect()
        # Stop after one yield by signaling the running flag off.
        books: list[OrderBook] = []
        async for book in stream.listen():
            books.append(book)
            stream._running = False  # exit the loop after the first yield
            break

    assert len(books) == 1
    assert books[0].token_id == "0xtoken123"
    cached = stream.get_orderbook("0xtoken123")
    assert cached is not None
    assert cached.best_bid == 0.50


@pytest.mark.asyncio
async def test_listen_skips_non_book_messages() -> None:
    other = {"event_type": "price", "asset_id": "0xx", "price": "0.5"}
    book_msg = json.dumps(SAMPLE_BOOK_MSG)
    ws = _make_ws([json.dumps(other), book_msg])
    with patch(
        "polymarket_execution.clob_ws.orderbook.websockets.connect",
        new=AsyncMock(return_value=ws),
    ):
        stream = OrderBookStream()
        await stream.connect()
        books: list[OrderBook] = []
        async for book in stream.listen():
            books.append(book)
            stream._running = False
            break

    assert len(books) == 1
    assert books[0].token_id == "0xtoken123"


# --- State accessors ---


def test_state_accessors_return_none_for_unknown_token() -> None:
    stream = OrderBookStream()
    assert stream.get_orderbook("missing") is None
    assert stream.get_best_bid("missing") is None
    assert stream.get_best_ask("missing") is None
    assert stream.get_mid_price("missing") is None


def test_state_accessors_return_cached_values() -> None:
    stream = OrderBookStream()
    book = OrderBook(
        token_id="0xtok",
        bids=[OrderBookLevel(0.50, 10)],
        asks=[OrderBookLevel(0.52, 5)],
    )
    stream._orderbooks["0xtok"] = book
    assert stream.get_orderbook("0xtok") is book
    assert stream.get_best_bid("0xtok") == 0.50
    assert stream.get_best_ask("0xtok") == 0.52
    assert stream.get_mid_price("0xtok") == pytest.approx(0.51)
