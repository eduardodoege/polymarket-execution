# CLI

A Typer-based CLI that mirrors the library surface. Useful for ops tasks
without writing a script.

```bash
polymarket-execution --help
```

## Command groups

| Group | Purpose |
|-------|---------|
| `redeem` | Discover, redeem, wrap (USDC.e -> pUSD) |
| `markets crypto` | Discover crypto up/down markets — native, no extra needed |
| `markets list` / `markets show` | General listing/search (requires `[markets]` extra) |
| `stop-loss` | Run a stop-loss monitor in the foreground |
| `take-profit` | Run a take-profit monitor in the foreground |
| `orders` | Place orders, fetch true VWAP fill price |
| `position` | Reconcile CLOB and on-chain positions |

## Environment variables

The CLI reads sensible defaults from environment so you don't have to
pass credentials on every command:

| Variable | Used by |
|----------|---------|
| `POLYGON_RPC_URL` | `redeem`, `position` |
| `POLYMARKET_PRIVATE_KEY` | order-placing commands (when wired up) |
| `POLYMARKET_SAFE` | `redeem`, `position` (Safe wallet mode) |

## Implementation note

The CLI is a thin layer over the library — every command builds the
relevant library object, calls one method, and prints the result. There
is no CLI-only logic. Anything you can do in the CLI you can also do
programmatically with the same arguments.
