# Architecture

`polymarket-execution` is a thin layer that sits between the raw Polymarket
CLOB v2 primitives (`py-clob-client-v2`) and a production trading bot. It
provides the plumbing — stop-loss, take-profit, redeem, position
reconciliation, order lifecycle, and recovery layers — while leaving
strategy decisions to the user.

## Design principles

1. **Modularity** — every module is usable in isolation. Need only the
   redeem flow? Import `polymarket_execution.redeem` and ignore the rest.
2. **Dependency injection** — the library never owns a `ClobClient`; it
   accepts one as a constructor argument. You pick the SDK
   (`py-clob-client-v2`, `polymarket-apis`, your own wrapper).
3. **Pluggable hooks** — price source, retry policy, exit predicate are
   callables, not configuration. Avoids the "I want TWAP / oracle / X"
   issue tree.
4. **Type hints everywhere** — `mypy --strict` passes.
5. **Stdlib logging** — no `structlog` requirement. Recovery layers emit
   structured records via standard `logging.LogRecord.extra`.
6. **Async-first where it matters** — monitor loops and WebSocket feeds
   are `async`. Redeem and position calls are sync (single-shot).
7. **Fail explicit** — money-touching code raises specific exceptions
   (see `polymarket_execution.exceptions`), never generic ones.

## Module map

```
polymarket_execution/
├── constants.py          Public protocol constants and contract addresses
├── exceptions.py         Custom exception hierarchy
├── price_reference.py    Pluggable price-source callables (mid/bid/ask/last)
├── price_feed/           Async price feeds (ChainLink RTDS)
├── triggers/             Stop-loss + take-profit monitors
├── redeem/               Discover, redeem, wrap (USDC.e -> pUSD)
├── orders/               Place orders, get true VWAP fill price
├── recovery.py           5 recovery layers for masked fills
├── markets/              Market discovery
│   ├── crypto.py         Native slug-based crypto up/down lookup (no extra)
│   └── general.py        Listing/search via polymarket-apis ([markets] extra)
├── position.py           CLOB ↔ chain reconciliation
├── order_lifecycle.py    Retry, replace, stale detection
└── cli/                  Typer CLI mirroring the library surface
```

## Boundary with the strategy layer

This library executes decisions; it does not make them. Decisions like
"when to enter a market", "how much to stake", "when to take profit" live
in your strategy code. The library exposes the smallest possible surface
needed to act on those decisions correctly.
