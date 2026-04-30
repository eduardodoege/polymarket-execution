"""Example: redeem all winnings from resolved markets.

Demonstrates the v0.1.0 module — discover, redeem, wrap USDC.e -> pUSD.

Usage:
    POLYGON_RPC_URL=https://polygon-rpc.com \\
    POLYMARKET_PRIVATE_KEY=0x... \\
    POLYMARKET_SAFE=0x... \\
    python examples/simple_redeem.py
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    rpc_url = os.environ["POLYGON_RPC_URL"]
    private_key = os.environ["POLYMARKET_PRIVATE_KEY"]
    safe_address = os.environ.get("POLYMARKET_SAFE")  # optional — None for EOA

    # NOTE: replace with your real CLOB client construction once you wire it up.
    # from py_clob_client_v2 import ClobClient
    # clob = ClobClient(host="https://clob.polymarket.com", chain_id=137,
    #                   key=private_key, signature_type=2, funder=safe_address)

    from polymarket_execution.redeem import RedeemClient

    redeemer = RedeemClient(
        clob_client=None,  # plug in your ClobClient
        web3_rpc_url=rpc_url,
        safe_address=safe_address,
        signer_private_key=private_key,
    )

    result = redeemer.auto_redeem_all()
    print(f"Redeemed {len(result.redeemed_markets)} markets")
    print(f"Wrap TX: {result.wrap_tx_hash} ({result.wrap_amount_usdc:.4f} USDC.e -> pUSD)")
    if result.failed_markets:
        print(f"Failures: {result.failed_markets}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
