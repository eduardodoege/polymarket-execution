# example_bot — Crypto Demo

A reference bot built on `polymarket-execution`. Demonstrates how to wire
the library's modules together into a complete trading loop, using a
deliberately trivial strategy.

## ⚠️ READ THIS BEFORE RUNNING

**This bot will lose money in production.** It exists to demonstrate
*how to compose the library*, NOT as a tradeable strategy.

- The decision rule is "buy the favorite when consensus crosses
  `min_consensus`", with zero tuning, zero backtest, zero edge.
- It is deliberately stupid so nobody copies it without thinking.
- Real edge lives in YOUR code, NOT in this file.

If you treat this bot as a turnkey trading system, you will lose money,
and that is your fault. Use it as a skeleton: plug your own decision
logic in, backtest before going live, size positions correctly, and
expect the unexpected.

## What the bot does each cycle

1. Discovers the current crypto up/down market via `markets.crypto`.
   The strike price (PTB) is resolved internally against ChainLink RTDS.
2. Subscribes to the YES/NO orderbooks via `clob_ws.OrderBookStream`.
3. Inside a configurable trading window
   (`min_minutes_in_cycle` / `max_minutes_remaining`), logs a
   hypothetical `WOULD BUY` decision when criteria match.
4. **Order placement lands in v0.4** — until then the bot is
   observation-only and never sends orders. The `WOULD BUY` log line
   shows what a real execution path would have done.
5. After the block ends, sweeps redeemable positions via `redeem` so
   winnings from previous cycles become spendable pUSD.
6. Sleeps to the next block boundary and repeats.

## Run

```bash
# From the repository root:
pip install -e .
pip install -r examples/example_bot/requirements.txt

# 1) Tuning (non-secret) -- edit to taste.
cp examples/example_bot/config.example.yaml examples/example_bot/config.yaml

# 2) Secrets -- private key, optional RPC URL with API key, etc.
#    .env is gitignored; .env.example is the safe template.
cp examples/example_bot/.env.example examples/example_bot/.env
# Edit .env: set POLYMARKET_PRIVATE_KEY for the EOA that signs the
# redeem transactions. Leave it blank to run in pure observation mode
# (no chain transactions at all).

python examples/example_bot/bot.py --config examples/example_bot/config.yaml
```

The bot loads `.env` automatically when it sits next to your
`config.yaml` (via `python-dotenv`). Ctrl-C to stop.

> **Use a dedicated wallet for first runs.** Create a fresh MetaMask
> account, fund it with $5-10 + a tiny bit of POL for gas, complete
> Polymarket onboarding once in the UI so the Safe is created, then
> use that EOA's private key here. Never use a wallet that holds
> meaningful funds.

## Capability map by `polymarket-execution` version

| Library version | example_bot capability |
|---|---|
| **v0.2 (current)** | Discovery + ChainLink PTB + orderbook stream + auto-redeem (observation only — `WOULD BUY` log lines, no orders sent) |
| v0.3 | + stop-loss / take-profit on open positions |
| v0.4 | + order placement (bot becomes live, no longer observation-only) + masked-fill recovery |
| v0.5 | + position reconciliation across CLOB and chain |

## What this bot does NOT include

- **Trading edge** — picking *what* to trade and *when*. That's your job.
- **Position sizing / stake escalation.** Default is the Polymarket minimum.
- **Market selection** beyond the configured symbol+window.
- **Backtesting infrastructure.**
- **Anything resembling a tested live strategy.**
