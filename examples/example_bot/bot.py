"""Reference crypto demo bot built on ``polymarket-execution``.

⚠️  THIS BOT WILL LOSE MONEY IN PRODUCTION ⚠️

It exists to demonstrate how to compose the library's modules — market
discovery (``markets.crypto``), the ChainLink price feed
(``price_feed.chainlink_rtds``, used internally by ``markets.crypto`` to
resolve the strike), orderbook subscription (``clob_ws``), and position
redemption (``redeem``) — into a complete trading loop. The strategy is
deliberately trivial: it picks the favorite side once consensus passes
a threshold inside a fixed time window, with zero edge, zero tuning, and
no backtest behind any number.

Real edge lives in YOUR code, NOT in this file.

What the bot does each cycle:

1. Discover the current crypto up/down market for the configured symbol +
   window via ``markets.crypto``. The strike price (PTB) is resolved
   internally against ChainLink RTDS.
2. Subscribe to the YES/NO orderbooks via ``clob_ws.OrderBookStream``.
3. Inside the trading window, log a hypothetical ``WOULD BUY`` decision
   when consensus crosses ``min_consensus``.
4. **Order placement lands in v0.4.** Until then the bot is
   observation-only and never sends orders. The ``WOULD BUY`` log line
   shows what a real execution path would have done.
5. After the block ends, sweep redeemable positions (``redeem``) so any
   winnings from prior cycles become spendable pUSD.
6. Sleep to the next block boundary and repeat.

See ``README.md`` for setup and the per-version capability map.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, fields
from pathlib import Path
from types import FrameType

import yaml

from polymarket_execution.clob_ws import OrderBookStream
from polymarket_execution.markets import discover_current_market
from polymarket_execution.markets.crypto import BLOCK_DURATIONS_S, CryptoMarket

log = logging.getLogger("example_bot")


@dataclass
class BotConfig:
    """Configuration loaded from YAML. See ``config.example.yaml``.

    Secrets (private keys, RPC URLs with embedded API keys) live in
    ``.env`` — see ``.env.example`` — not in this YAML.
    """

    symbol: str = "btc"
    window: str = "5m"
    min_consensus: float = 0.85
    min_minutes_in_cycle: float = 2.0
    max_minutes_remaining: float = 4.0
    poll_interval_s: float = 5.0
    exit_buffer_s: float = 10.0
    redeem_after_cycle: bool = True
    log_level: str = "INFO"

    @classmethod
    def load(cls, path: Path) -> BotConfig:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"config must be a YAML mapping, got {type(raw).__name__}")
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        return cls(**{k: v for k, v in raw.items() if k in known})

    def validate(self) -> None:
        if self.window not in BLOCK_DURATIONS_S:
            raise ValueError(
                f"unsupported window {self.window!r}; pick one of {sorted(BLOCK_DURATIONS_S)}"
            )
        if not 0.0 < self.min_consensus < 1.0:
            raise ValueError("min_consensus must be in (0, 1)")
        if self.poll_interval_s <= 0:
            raise ValueError("poll_interval_s must be positive")


class CryptoDemoBot:
    """Trivial crypto up/down observation bot — composition demo only."""

    def __init__(self, config: BotConfig, *, private_key: str | None = None) -> None:
        self.config = config
        self._private_key = private_key
        self._block_duration_s = BLOCK_DURATIONS_S[config.window]
        self._stop_event = asyncio.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        log.warning("=" * 70)
        log.warning("DEMO BOT — observation only, no orders sent (v0.4 lands orders).")
        log.warning("Strategy is trivial. This will lose money in production.")
        log.warning("=" * 70)

        while not self._stop_event.is_set():
            try:
                await self._cycle()
            except Exception as exc:
                log.error("cycle failed: %s", exc, exc_info=True)

            if self._stop_event.is_set():
                break

            if self.config.redeem_after_cycle and self._private_key:
                await self._redeem_sweep()

            await self._wait_next_block()

        log.info("bot stopped")

    async def _cycle(self) -> None:
        market = await asyncio.to_thread(
            discover_current_market, self.config.symbol, window=self.config.window
        )
        if market is None:
            log.warning(
                "market for %s/%s not yet listed; skipping",
                self.config.symbol.upper(),
                self.config.window,
            )
            return

        ptb = f"${market.price_to_beat:,.2f}" if market.price_to_beat else "?"
        log.info(
            "cycle: %s %s YES=%.2f NO=%.2f PTB=%s remaining=%.1fmin",
            market.symbol.upper(),
            market.window,
            market.yes_price,
            market.no_price,
            ptb,
            market.minutes_remaining,
        )

        async with OrderBookStream() as stream:
            await stream.subscribe([market.yes_token_id, market.no_token_id])
            await self._observe_until_block_end(market, stream)

    async def _observe_until_block_end(self, market: CryptoMarket, stream: OrderBookStream) -> None:
        listen_task = asyncio.create_task(self._drain_books(stream))
        try:
            decision_logged = False
            deadline = market.block_end - self.config.exit_buffer_s
            while time.time() < deadline and not self._stop_event.is_set():
                if not decision_logged and self._can_trade(market):
                    decision = self._decide(market, stream)
                    if decision is not None:
                        log.info("WOULD %s — observation only (orders land in v0.4)", decision)
                        decision_logged = True
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.config.poll_interval_s
                    )
        finally:
            listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listen_task

    @staticmethod
    async def _drain_books(stream: OrderBookStream) -> None:
        """Drive the book-update generator so the per-token cache stays fresh."""
        async for _book in stream.listen():
            pass

    def _can_trade(self, market: CryptoMarket) -> bool:
        elapsed_min = (time.time() - market.block_start) / 60
        if elapsed_min < self.config.min_minutes_in_cycle:
            return False
        return market.minutes_remaining <= self.config.max_minutes_remaining

    def _decide(self, market: CryptoMarket, stream: OrderBookStream) -> str | None:
        yes_book = stream.get_orderbook(market.yes_token_id)
        no_book = stream.get_orderbook(market.no_token_id)
        yes_bid = yes_book.best_bid if yes_book else None
        no_bid = no_book.best_bid if no_book else None
        if yes_bid is None or no_bid is None:
            return None
        favorite_bid = max(yes_bid, no_bid)
        if favorite_bid < self.config.min_consensus:
            return None
        side = "YES" if yes_bid > no_bid else "NO"
        return f"BUY {side} @ ${favorite_bid:.4f}"

    async def _redeem_sweep(self) -> None:
        from polymarket_execution.redeem import RedeemClient

        private_key = self._private_key
        assert private_key is not None  # guarded in run()

        rpc_url = os.environ.get("POLYGON_RPC_URL") or None

        def _do_sweep() -> None:
            with RedeemClient(
                private_key=private_key, rpc_url=rpc_url, signature_type=2
            ) as redeemer:
                result = redeemer.auto_redeem_all()
            if result.redeemed_markets:
                log.info(
                    "redeemed %d market(s); wrap_tx=%s",
                    len(result.redeemed_markets),
                    result.wrap_tx_hash or "n/a",
                )
            if result.failed_markets:
                log.warning(
                    "%d redeem failure(s) (will retry next cycle)",
                    len(result.failed_markets),
                )

        try:
            await asyncio.to_thread(_do_sweep)
        except Exception as exc:
            log.error("redeem sweep failed: %s", exc, exc_info=True)

    async def _wait_next_block(self) -> None:
        now = time.time()
        next_block_start = (int(now) // self._block_duration_s + 1) * self._block_duration_s
        sleep_for = max(0.0, next_block_start - now)
        log.info("sleeping %.1fs until next block", sleep_for)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_for)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="example_bot -- demo crypto observation bot for polymarket-execution"
    )
    parser.add_argument("--config", type=Path, required=True, help="Path to config YAML")
    return parser.parse_args(argv)


def _try_load_dotenv(config_path: Path) -> None:
    """Best-effort load of `.env` next to the config (or in CWD).

    No-op if `python-dotenv` is not installed — the user can still
    `export` env vars manually.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    candidate = config_path.parent / ".env"
    if candidate.is_file():
        load_dotenv(candidate)
    else:
        load_dotenv()  # falls back to CWD


async def _run_main(config_path: Path) -> int:
    _try_load_dotenv(config_path)
    config = BotConfig.load(config_path)
    config.validate()
    logging.basicConfig(
        level=config.log_level, format="%(asctime)s %(levelname)s %(name)s | %(message)s"
    )

    private_key = os.environ.get("POLYMARKET_PRIVATE_KEY")
    if config.redeem_after_cycle and not private_key:
        log.warning(
            "POLYMARKET_PRIVATE_KEY not set; auto-redeem disabled. "
            "Bot continues in pure observation mode."
        )

    bot = CryptoDemoBot(config, private_key=private_key)
    loop = asyncio.get_running_loop()

    def _stop(_signum: int, _frame: FrameType | None) -> None:
        log.info("stop requested")
        loop.call_soon_threadsafe(bot.request_stop)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    await bot.run()
    return 0


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run_main(args.config))


if __name__ == "__main__":
    sys.exit(main())


# Re-export for tests / external introspection.
__all__ = ["BotConfig", "CryptoDemoBot", "main"]
