# Redeem

Claim winnings from resolved Polymarket positions, then wrap any USDC.e
proceeds to pUSD (required after the CLOB v2 cutover on 2026-04-28).

## Quick example

```python
import logging
from polymarket_execution.redeem import RedeemClient

logging.basicConfig(level=logging.INFO)

with RedeemClient(
    private_key=PRIVATE_KEY,
    rpc_url=POLYGON_RPC_URL,           # optional; defaults to public Polygon RPCs
    signature_type=2,                  # 2 = Gnosis Safe (default); 0 = EOA
) as redeemer:
    result = redeemer.auto_redeem_all()

print(result.redeemed_markets)        # list of condition_ids redeemed
print(result.failed_markets)          # list of (condition_id, error_message)
print(result.wrap_tx_hash)            # tx hash of the USDC.e -> pUSD wrap, if it ran
print(result.total_gas_cost_pol)      # total gas spent (sweep + wrap)
```

## What happens under the hood

1. **`discover_redeemable()`** queries the Polymarket Data API
   (`/positions?user=<wallet>&redeemable=true`) and returns
   `RedeemablePosition` rows for resolved markets where the wallet still
   holds shares. Empty rows and ones already redeemed in this session are
   skipped.
2. **`redeem_market(condition_id, yes_shares, no_shares, neg_risk=False)`**
   calls `ConditionalTokens.redeemPositions` via the underlying
   `polymarket-apis` client. Returns a `RedeemReceipt` with `tx_hash`,
   `gas_used`, and `gas_cost_pol`.
3. **`auto_redeem_all()`** ties the two together and ends with
   `wrap_usdce_to_pusd()` so the proceeds are visible to the V2
   collateral view.

## Why the wrap step exists

Polymarket migrated its collateral from **USDC.e** (V1) to **pUSD** (V2)
on 2026-04-28. `polymarket-apis` redeem still pays winnings in USDC.e.
The V2 CLOB only sees pUSD as collateral, so without wrapping the
redeemed funds sit idle and the bot's balance view does not reflect them.

`RedeemClient.auto_redeem_all` always runs `wrap_usdce_to_pusd` after a
successful sweep. It's idempotent (no-op when balance is zero) and
best-effort (a wrap failure does not invalidate the redeems — the USDC.e
stays in your wallet for the next session to pick up).

To skip the wrap (e.g., if you handle it yourself), pass
`wrap_after_redeem=False` to `RedeemClient`.

## Safe wallet support

Polymarket's `signature_type=2` (`POLY_GNOSIS_SAFE`) custodies positions
in a Gnosis Safe. Pass `signature_type=2` to `RedeemClient` (the default)
and Safe routing happens automatically — `polymarket-apis` builds an
`execTransaction` call signed by the EOA private key.

For EOA-only mode (no Safe), pass `signature_type=0`.

## RPC fallback

`RedeemClient` ships with a list of public Polygon RPC endpoints
(`DEFAULT_POLYGON_RPC_URLS` in `polymarket_execution.constants`). On
RPC-level errors (rate limit, gateway, connection), it transparently
switches to the next endpoint in the list and retries. Pass
`rpc_url=` to set your preferred RPC (it goes to the front of the
fallback chain).

## CLI

```bash
polymarket-execution redeem auto              # discover + redeem + wrap
polymarket-execution redeem list --wallet 0x  # dry-run discovery (placeholder, not implemented yet)
polymarket-execution redeem market 0xCID...   # redeem one market (placeholder, not implemented yet)
```

## Errors

| Exception | Raised when |
|---|---|
| `RedeemError` | Data API call failed, or web3 client cannot be initialised |
| `WrapError` | Wrap transaction was submitted but reverted |

`RedeemReceipt.success == False` for per-market failures during
`auto_redeem_all`; the sweep continues with the next market. Inspect
`result.failed_markets` for the list.
