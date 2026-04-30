# Stop-loss

Monitor a position's reference price and fire a market exit when the price
crosses your trigger.

## Quick example

```python
from polymarket_execution.triggers import StopLossMonitor
from polymarket_execution.price_reference import use_mid_price

monitor = StopLossMonitor(clob_client=clob, price_source=use_mid_price)
monitor.add_stop(token_id="0x...", trigger_price=0.45, size=100, side="long")
await monitor.run()
```

## Choosing a price source

The `price_source` parameter is a callable, not a config string. Built-in
choices in `polymarket_execution.price_reference`:

- `use_mid_price` — average of best bid and best ask
- `use_best_bid` — most conservative for sells
- `use_best_ask`
- `use_last_trade_price`
- `with_offset(source, delta)` — wrap any source with an additive offset
- `fallback_chain(s1, s2, ...)` — try each in order, first non-`None` wins

You can also pass your own callable matching the signature
`(book) -> float | None`.

## Note on triggers vs decisions

The library is intentionally silent on **when** to arm a stop-loss or
**what trigger** to use. Those are strategy decisions. The library handles
the mechanic (monitor, fire, exit) and the recovery (fill detection,
masked-fill layers).

## CLI

```bash
polymarket-execution stop-loss watch 0xTOKEN --trigger 0.45 --size 100
```
