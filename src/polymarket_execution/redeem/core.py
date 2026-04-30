"""Core redeem logic — discover resolved positions, claim winnings, wrap proceeds.

Designed for both EOA wallets and Gnosis Safes. When ``safe_address`` is
provided, redeem calls are routed through ``SafeRedeemAdapter``; otherwise
the signer wallet is used directly.

Workflow
--------
1. Query CLOB / chain for positions held in resolved markets.
2. For each market, call ``ConditionalTokens.redeemPositions(...)``.
3. After the loop, call ``wrap_usdce_to_pusd`` once (idempotent — no-op if
   USDC.e balance is zero).
4. Return a ``RedeemResult`` with TX hashes and amounts for each step.

Why the wrap step matters (CLOB v2)
-----------------------------------
``polymarket-apis 0.5.x`` redeem still pays winnings in USDC.e (the V1
collateral token). After the V2 cutover (28/04/2026) the bot reads its
balance via ``AssetType.COLLATERAL`` which now means **pUSD**, not USDC.e.
Without the wrap, redeemed USDC.e sits idle in the Safe and the bot can't see it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RedeemResult:
    """Summary of a redeem sweep."""

    redeemed_markets: list[str] = field(default_factory=list)
    """condition_ids of markets successfully redeemed."""

    failed_markets: list[tuple[str, str]] = field(default_factory=list)
    """(condition_id, error_message) for failures."""

    redeem_tx_hashes: list[str] = field(default_factory=list)
    """One TX hash per successful redeem."""

    wrap_tx_hash: str | None = None
    """TX hash of the post-redeem USDC.e -> pUSD wrap, if it ran."""

    wrap_amount_usdc: float = 0.0
    """Amount of USDC.e wrapped to pUSD (0 if no wrap was needed)."""


class RedeemClient:
    """High-level redeem client — discover, redeem, wrap, report."""

    def __init__(
        self,
        clob_client: Any,
        web3_rpc_url: str,
        safe_address: str | None = None,
        signer_private_key: str | None = None,
    ) -> None:
        self.clob_client = clob_client
        self.web3_rpc_url = web3_rpc_url
        self.safe_address = safe_address
        self.signer_private_key = signer_private_key

    def discover_redeemable(self) -> list[str]:
        """Return condition_ids of resolved markets where the wallet has unredeemed shares."""
        raise NotImplementedError("v0.1.0: query CLOB positions + chain to find redeemable markets")

    def redeem_market(self, condition_id: str) -> str:
        """Redeem a single market. Returns the redeem TX hash."""
        raise NotImplementedError("v0.1.0: call ConditionalTokens.redeemPositions for one market")

    def auto_redeem_all(self) -> RedeemResult:
        """Discover and redeem all eligible markets, then wrap USDC.e -> pUSD.

        Idempotent and best-effort: failures on individual markets do not stop the sweep.
        The wrap step is always attempted at the end (no-op if USDC.e == 0).
        """
        raise NotImplementedError(
            "v0.1.0: discover, loop redeem_market, then wrap_usdce_to_pusd, return RedeemResult"
        )
