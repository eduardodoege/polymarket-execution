# Take-profit

Monitor a position's PnL or absolute price and fire a market exit when
your profit target is hit.

## Quick example

```python
from polymarket_execution.triggers import TakeProfitMonitor
from polymarket_execution.price_reference import use_mid_price

monitor = TakeProfitMonitor(clob_client=clob, price_source=use_mid_price)
monitor.add_take_profit(
    token_id="0x...",
    size=100,
    entry_price=0.50,
    target_pnl_pct=0.10,   # exit at +10% PnL
)
await monitor.run()
```

## PnL target vs absolute price target

Pass exactly one of:

- `target_pnl_pct` — fractional PnL (e.g., `0.10` for +10%)
- `target_price` — absolute price level

Passing both, or neither, raises `ValueError`.

## Why a separate module from stop-loss

The underlying loop is shared (see `triggers.base.TriggerMonitor`), but
the inputs differ: take-profit needs entry price to compute PnL, stop-loss
only needs current price. Keeping the public API split makes intent
obvious at the call site.

## CLI

```bash
polymarket-execution take-profit watch 0xTOKEN \
    --entry-price 0.50 --target-pct 0.10 --size 100
```
