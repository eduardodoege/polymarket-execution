"""Redeem winnings from resolved Polymarket positions.

Three modules:

- ``core`` — discover redeemable positions, call ``redeemPositions`` on chain
- ``wrap`` — convert USDC.e to pUSD after redeem (CLOB v2 requirement)
- ``safe`` — Gnosis Safe wallet helpers (Safe routing itself is built into
  the underlying ``polymarket-apis`` client when ``signature_type=2``)

The default entry point ``RedeemClient`` composes all three: it discovers
resolved positions, redeems them, and wraps any USDC.e proceeds to pUSD
in a single sweep.
"""

from polymarket_execution.redeem.core import (
    RedeemablePosition,
    RedeemClient,
    RedeemReceipt,
    RedeemResult,
)
from polymarket_execution.redeem.safe import SafeRedeemAdapter
from polymarket_execution.redeem.wrap import WrapReceipt, wrap_usdce_to_pusd

__all__ = [
    "RedeemablePosition",
    "RedeemClient",
    "RedeemReceipt",
    "RedeemResult",
    "SafeRedeemAdapter",
    "WrapReceipt",
    "wrap_usdce_to_pusd",
]
