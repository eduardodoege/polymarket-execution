# example_bot

A complete reference bot built on `polymarket-execution`. Demonstrates how
to wire the library's modules together into a production-shaped flow,
without committing to any particular trading strategy.

> **Status:** evolves alongside the library. Each release of
> `polymarket-execution` upgrades this example to use the new module(s).

| polymarket-execution version | example_bot capability |
|------------------------------|-----------------------|
| v0.1.0 | Auto-redeem on a schedule (current minimum bot) |
| v0.2.0 | + Position reconciliation report |
| v0.3.0 | + Stop-loss + take-profit on a single open position |
| v0.4.0 | + Order placement + lifecycle (retry / replace) |
| v0.5.0 | + Market discovery + full CLI parity |

## Setup

```bash
# From the repository root:
pip install -e .
cp examples/example_bot/config.example.yaml examples/example_bot/config.yaml
# Edit config.yaml with your credentials and settings
python examples/example_bot/bot.py --config examples/example_bot/config.yaml
```

## What the bot does NOT include

By design, the example bot does **not** include:

- Trading strategy (when / what / how much to trade)
- Position sizing logic
- Market selection heuristics
- Backtesting

Those are out of scope for `polymarket-execution`. The example bot picks
markets and sizes from the config file you provide, and uses the library
to execute the resulting decisions.
