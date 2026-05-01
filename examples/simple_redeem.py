"""Example: redeem all winnings from resolved markets.

Demonstrates the v0.1 redeem module — discover, redeem, and wrap any
USDC.e proceeds to pUSD (CLOB v2 fix).

Usage:
    POLYGON_RPC_URL=https://polygon-rpc.com \\
    POLYMARKET_PRIVATE_KEY=0x... \\
    python examples/simple_redeem.py
"""

from __future__ import annotations

import logging
import os
import sys


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s"
    )

    private_key = os.environ["POLYMARKET_PRIVATE_KEY"]
    rpc_url = os.environ.get("POLYGON_RPC_URL")  # optional; falls back to public RPCs

    from polymarket_execution.redeem import RedeemClient

    with RedeemClient(
        private_key=private_key,
        rpc_url=rpc_url,
        signature_type=2,  # 2 = Gnosis Safe (Polymarket default); use 0 for EOA-only
    ) as redeemer:
        result = redeemer.auto_redeem_all()

    print(f"Redeemed {len(result.redeemed_markets)} market(s)")
    print(f"Failures: {len(result.failed_markets)}")
    if result.wrap_tx_hash:
        print(
            f"Wrapped {result.wrap_amount_usdc:.4f} USDC.e -> pUSD "
            f"(tx={result.wrap_tx_hash[:20]}...)"
        )
    print(f"Total gas: {result.total_gas_used:,} units (~{result.total_gas_cost_pol:.6f} POL)")

    return 1 if result.failed_markets else 0


if __name__ == "__main__":
    sys.exit(main())
