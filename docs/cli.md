# CLI

A Typer-based CLI that mirrors the library surface. Useful for ops tasks
without writing a script.

```bash
polymarket-execution --help
```

## Command groups (current)

| Group | Purpose |
|-------|---------|
| `redeem` | Discover, redeem, wrap (USDC.e -> pUSD) |
| `markets crypto` | Discover crypto up/down markets (native, slug-based) |

New sub-commands (`stop-loss`, `take-profit`, `orders`, `position`,
`markets list`/`show`) ship together with the library feature they
expose — we don't register placeholders that would raise
`NotImplementedError` at runtime.

## Environment variables

The CLI reads sensible defaults from environment so you don't have to
pass credentials on every command:

| Variable | Used by |
|----------|---------|
| `POLYGON_RPC_URL` | `redeem` |
| `POLYMARKET_PRIVATE_KEY` | `redeem` (and order-placing commands when they land) |

## Implementation note

The CLI is a thin layer over the library — every command builds the
relevant library object, calls one method, and prints the result. There
is no CLI-only logic. Anything you can do in the CLI you can also do
programmatically with the same arguments.
