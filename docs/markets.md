# Markets

Two modules cover different needs:

- **`markets.crypto`** — native discovery for Polymarket crypto up/down markets (BTC/ETH/SOL/XRP at 5m/15m/1h windows). One HTTP call per lookup against the Gamma API.
- **`markets.general`** — paginated listing, search, and category filtering for arbitrary markets (politics, sports, etc.). Delegates to `polymarket-apis` (a core dependency since v0.2).

For deterministic crypto lookup, use `crypto`. For everything else, use `general`.

## Crypto markets

Polymarket runs a continuous series of binary up/down markets at fixed time windows. Each market is identified by a deterministic slug:

```
{symbol}-updown-{window}-{block_timestamp}
```

`block_timestamp` is the Unix epoch rounded down to the nearest window boundary (`ts - (ts % window_seconds)`). Because the slug is fully predictable, we compute it locally and fetch one market at a time — no listing, no pagination.

### Quick example

```python
from polymarket_execution.markets import discover_current_markets

# All four default symbols (btc, eth, sol, xrp) at 5m
markets = discover_current_markets(window="5m")
for m in markets:
    print(m)
    print("  URL:", m.polymarket_url)
    print("  Strike:", m.price_to_beat)
    print("  Token IDs:", m.yes_token_id, m.no_token_id)
```

### Single symbol

```python
from polymarket_execution.markets import discover_current_market

btc = discover_current_market("btc", window="15m")
if btc is None:
    print("Market for current 15m block not yet listed (try again in a few seconds)")
else:
    print(btc.minutes_remaining, "minutes left")
```

### Reusing the HTTP client

For high-frequency polling, instantiate `CryptoMarketDiscovery` once and reuse:

```python
from polymarket_execution.markets import CryptoMarketDiscovery

with CryptoMarketDiscovery(window="5m") as discovery:
    while True:
        markets = discovery.discover_markets()
        # ... process ...
```

### Supported windows and symbols

| Window | Duration |
|---|---|
| `5m` | 300 s |
| `15m` | 900 s |
| `1h` | 3600 s |

Default symbols: `btc`, `eth`, `sol`, `xrp`. Pass any list to `discover_markets(symbols=[...])` to override.

## General markets

For listing, search, and filtering across all market categories:

```python
from polymarket_execution.markets.general import list_markets

active = list_markets(active=True, limit=100)
```

Status: skeleton in v0.1, full implementation in v0.5.0.

## CLI

```bash
polymarket-execution markets crypto                          # all default symbols at 5m
polymarket-execution markets crypto --symbol btc --window 15m  # single symbol, 15m
polymarket-execution markets list                            # general listing
polymarket-execution markets show <condition_id>             # market details
```
