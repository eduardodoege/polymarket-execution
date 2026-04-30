"""USDC.e -> pUSD wrap via ``CollateralOnramp.wrap`` (CLOB v2 collateral migration).

Why this exists
---------------
Polymarket migrated its collateral from USDC.e (V1) to pUSD (V2) on
2026-04-28. ``polymarket-apis`` redeems still pay out in USDC.e, but the
V2 CLOB only sees pUSD as collateral. Without wrapping, redeemed funds
sit idle and the bot cannot use them.

Behaviour
---------
- **Idempotent**: returns ``None`` immediately if the USDC.e balance is zero.
- **Best-effort**: caller should not let an exception here invalidate a
  successful redeem sweep — wrap can be retried next session.
- **Cheap**: ~131,232 gas (~$0.0175 POL at typical Polygon prices).
- **Allowance**: assumes ``CollateralOnramp`` already has unlimited allowance
  on USDC.e (set automatically by V2 approve).

Contract addresses (Polygon mainnet, see ``polymarket_execution.constants``):

- ``USDCE_ADDRESS``: ``0x2791Bca1...``
- ``PUSD_ADDRESS``: ``0xC011a73e...``
- ``COLLATERAL_ONRAMP_ADDRESS``: ``0x93070a84...``
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WrapReceipt:
    """Outcome of a USDC.e -> pUSD wrap call."""

    tx_hash: str
    amount_usdc: float
    gas_used: int


def wrap_usdce_to_pusd(
    web3_rpc_url: str,
    wallet_address: str,
    signer_private_key: str | None = None,
    safe_address: str | None = None,
) -> WrapReceipt | None:
    """Wrap the wallet's full USDC.e balance to pUSD via CollateralOnramp.

    Pass either ``signer_private_key`` (for EOA) or ``safe_address`` (for
    Gnosis Safe — the signer must be an owner of the Safe). Exactly one
    is required when ``USDC.e balance > 0``.

    Returns ``None`` if balance is zero. Raises ``WrapError`` on failure.
    """
    raise NotImplementedError(
        "v0.1.0: read USDC.e balance, no-op if 0, else call CollateralOnramp.wrap "
        "(via Safe if safe_address given, else via signer EOA), return WrapReceipt"
    )
