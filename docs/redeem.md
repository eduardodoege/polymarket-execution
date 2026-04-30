# Redeem

Claim winnings from resolved Polymarket positions, then wrap any USDC.e
proceeds to pUSD (required after the CLOB v2 cutover on 2026-04-28).

## Quick example

```python
from py_clob_client_v2 import ClobClient
from polymarket_execution.redeem import RedeemClient

clob = ClobClient(host="https://clob.polymarket.com", chain_id=137,
                  key=PRIVATE_KEY, signature_type=2, funder=SAFE_ADDRESS)

redeemer = RedeemClient(
    clob_client=clob,
    web3_rpc_url=POLYGON_RPC,
    safe_address=SAFE_ADDRESS,
    signer_private_key=PRIVATE_KEY,
)

result = redeemer.auto_redeem_all()
print(result.redeemed_markets, result.wrap_tx_hash)
```

## Why the wrap step exists

Polymarket migrated its collateral from **USDC.e** (V1) to **pUSD** (V2)
on 2026-04-28. `polymarket-apis 0.5.x` redeem still pays winnings in
USDC.e. The V2 CLOB only sees pUSD as collateral, so without wrapping
the redeemed funds sit idle in your wallet/Safe and the bot's balance
view doesn't reflect them.

`RedeemClient.auto_redeem_all` always runs `wrap_usdce_to_pusd` after the
redeem loop. It's idempotent (no-op when balance is zero) and
best-effort (a wrap failure does not invalidate the redeems).

## Safe wallet support

Polymarket's `signature_type=2` (`POLY_GNOSIS_SAFE`) custodies positions
in a Gnosis Safe. Pass `safe_address=` to `RedeemClient` and the
`SafeRedeemAdapter` routes redeem and wrap calls through `execTransaction`
on the Safe.

## CLI

```bash
polymarket-execution redeem auto              # discover + redeem + wrap
polymarket-execution redeem list --wallet 0x  # dry-run discovery
polymarket-execution redeem market 0xCID...   # redeem one market
```
