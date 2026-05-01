# polymarket-execution

Execution utilities for Polymarket: stop-loss, redeem, position sync, order lifecycle, and market discovery.

Built on top of [`py-clob-client-v2`](https://github.com/Polymarket/py-clob-client-v2). Designed to be the missing layer between the raw [Polymarket](https://polymarket.com) CLOB v2 primitives and a production trading bot.

> **Status:** Early development (v0.1.x alpha). API may change before 1.0.

## Why this exists

The Polymarket CLOB gives you primitives like `create_and_post_order` and `cancel_order`, but doesn't help with the things you actually need to run a bot in production:

- **Stop-loss / take-profit execution** — CLOB has no native trigger orders
- **Redeeming resolved positions** — claim winnings via web3 (with the USDC.e → pUSD wrap dance that V2 introduced)
- **Position reconciliation** — keep CLOB and on-chain state in sync
- **Order lifecycle** — retry, replace, and clean up stale orders
- **Recovery layers** — detect masked fills when network errors / status timeouts / balance locks hide a successful order

This library provides those primitives, with no opinions about your trading strategy.

## Install

Requires Python 3.12+. We strongly recommend installing inside a virtual environment to keep dependencies isolated from your system Python:

```bash
python -m venv .venv
source .venv/Scripts/activate    # Git Bash on Windows
# .venv\Scripts\Activate.ps1     # PowerShell
# source .venv/bin/activate      # macOS / Linux

pip install polymarket-execution
```

Development extras (only needed if you're contributing):

```bash
pip install polymarket-execution[dev]       # pytest, ruff, mypy
```

## Quick start: discover current crypto markets

> Available now. Native slug-based lookup.

```python
from polymarket_execution.markets import discover_current_markets

markets = discover_current_markets(window="5m")  # btc, eth, sol, xrp by default
for m in markets:
    print(m, "->", m.polymarket_url, "PTB:", m.price_to_beat)
```

The strike price (`price_to_beat`) is resolved against Polymarket's
ChainLink RTDS feed at `block_start` — i.e., the same value the oracle
will use to settle the market. Pass `resolve_ptb=False` to skip the
WebSocket lookup if you don't need the strike (faster, no extra socket).

## Quick start: redeem resolved positions

> Available now (v0.1).

```python
from polymarket_execution.redeem import RedeemClient

with RedeemClient(
    private_key=PRIVATE_KEY,        # EOA hex private key
    rpc_url=POLYGON_RPC_URL,        # optional; falls back to public Polygon RPCs
    signature_type=2,               # 2 = Gnosis Safe (Polymarket default); 0 = EOA-only
) as redeemer:
    result = redeemer.auto_redeem_all()  # also wraps USDC.e -> pUSD afterwards

print(result.redeemed_markets, result.wrap_tx_hash)
```

## Quick start: stop-loss

> Preview API. Implementation lands in v0.3.0; the snippet below shows the target shape.

```python
from polymarket_execution.triggers import StopLossMonitor
from polymarket_execution.price_reference import use_mid_price

monitor = StopLossMonitor(clob_client=client, price_source=use_mid_price)
monitor.add_stop(token_id="0x...", trigger_price=0.45, size=100)
await monitor.run()
```

## Modules

| Module | Purpose |
|---|---|
| `redeem` | Claim USDC from resolved positions via web3 (with V2 USDC.e → pUSD wrap) |
| `triggers.stop_loss` | Monitor positions and execute market orders on trigger |
| `triggers.take_profit` | Monitor PnL and execute market orders on profit target |
| `orders.place` | Place orders with sane defaults |
| `orders.fills` | Get true VWAP fill price via `get_trades` (fixes a critical PnL bug) |
| `recovery` | 5 recovery layers for masked fills (network/status/balance/matched_orders/suspect_drop) |
| `position` | Reconcile CLOB and on-chain positions |
| `markets.crypto` | Native slug-based discovery for crypto up/down markets |
| `markets.general` | List/search arbitrary markets via polymarket-apis |
| `order_lifecycle` | Retry, replace, and clean up stale orders |
| `price_feed.chainlink_rtds` | Polymarket-aligned ChainLink price feed via WebSocket (one-shot snapshot lookup available now; streaming lands with `triggers` in v0.3) |

## CLI

```bash
polymarket-execution redeem auto                          # redeem all resolved positions
polymarket-execution markets crypto --window 5m           # current crypto markets
polymarket-execution markets crypto --symbol btc          # single symbol
polymarket-execution markets crypto --window 5m --no-ptb  # skip ChainLink PTB lookup (faster)
polymarket-execution markets list                         # general listing
polymarket-execution stop-loss watch                      # interactive stop-loss monitor
polymarket-execution take-profit watch                    # interactive take-profit monitor
polymarket-execution position reconcile                   # CLOB vs chain drift report
```

Run `polymarket-execution --help` for the full command tree.

## Development

Working on the library itself? Clone and install editable inside a venv:

```bash
git clone https://github.com/eduardodoege/polymarket-execution.git
cd polymarket-execution

python -m venv .venv
source .venv/Scripts/activate    # see install section for other shells
pip install -e ".[dev]"          # editable + dev tooling

# The same checks CI runs
ruff check .
ruff format --check .
mypy src/
pytest
```

`pyproject.toml` sets `pythonpath = ["src"]` for pytest so tests work without an editable install, but `pip install -e .` is needed for `mypy` and the CLI entry point. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the PR workflow.

## What this is NOT

- **A trading framework.** You decide when, what, and how much to trade.
- **A strategy library.** No signals, no parameters, no backtesting.
- **A replacement for `py-clob-client-v2`.** It plugs in on top.

## License

[MIT](./LICENSE)

## Sponsor

If this saves you time in production, [consider sponsoring](https://github.com/sponsors/eduardodoege).
