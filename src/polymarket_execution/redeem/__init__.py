"""Redeem winnings from resolved Polymarket positions.

Three modules:

- ``core`` — the actual ``redeemPositions`` web3 call(s)
- ``wrap`` — convert USDC.e to pUSD after redeem (CLOB v2 requirement)
- ``safe`` — Gnosis Safe wallet support (signature_type=2 / POLY_GNOSIS_SAFE)

The default entrypoint ``RedeemClient`` composes all three: it discovers
resolved positions, redeems them, and wraps any USDC.e proceeds to pUSD
in a single sweep.
"""

from polymarket_execution.redeem.core import RedeemClient, RedeemResult
from polymarket_execution.redeem.safe import SafeRedeemAdapter
from polymarket_execution.redeem.wrap import wrap_usdce_to_pusd

__all__ = ["RedeemClient", "RedeemResult", "SafeRedeemAdapter", "wrap_usdce_to_pusd"]
