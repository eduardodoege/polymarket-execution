"""Position reconciliation — compare CLOB view with on-chain reality.

Polymarket positions live in two places:

- **CLOB API** view: positions as the order matching engine sees them
  (``client.get_positions()``).
- **Chain**: the actual ``ConditionalTokens`` ERC-1155 balances on Polygon.

Most of the time these agree. They diverge in interesting ways:

- **Stale CLOB cache**: a fill happened on chain but CLOB hasn't indexed
  yet (~1-5s lag).
- **Safe vs signer custody**: positions held in a Gnosis Safe show in
  ``balanceOf(safe)`` but a signer-only query misses them.
- **Partial fills mid-flight**: a sell is matching across multiple price
  levels, balance is dropping, CLOB hasn't aggregated yet.
- **Manual moves**: someone transferred ERC-1155s out of band.

This module surfaces those divergences as a structured ``PositionDrift``
report so the caller can decide what to do (wait, retry, alert).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PositionRecord:
    """A position from one source (CLOB or chain)."""

    token_id: str
    quantity: float
    source: str  # "clob" or "chain"


@dataclass
class PositionDrift:
    """A reconciliation result — agreements and divergences."""

    in_sync: list[str] = field(default_factory=list)
    """token_ids where CLOB and chain agree (within tolerance)."""

    drifted: list[tuple[str, float, float]] = field(default_factory=list)
    """(token_id, clob_qty, chain_qty) where they disagree."""

    only_in_clob: list[PositionRecord] = field(default_factory=list)
    only_on_chain: list[PositionRecord] = field(default_factory=list)


class PositionReconciler:
    """Compare CLOB and chain positions for a wallet."""

    def __init__(
        self,
        clob_client: Any,
        web3_rpc_url: str,
        wallet_address: str,
        tolerance_shares: float = 0.01,
    ) -> None:
        self.clob_client = clob_client
        self.web3_rpc_url = web3_rpc_url
        self.wallet_address = wallet_address
        self.tolerance_shares = tolerance_shares

    def get_clob_positions(self) -> list[PositionRecord]:
        """Fetch positions as CLOB sees them."""
        raise NotImplementedError(
            "get_clob_positions is not implemented yet -- pending: call "
            "client.get_positions(), map to PositionRecord"
        )

    def get_chain_positions(self, token_ids: list[str]) -> list[PositionRecord]:
        """Fetch on-chain ERC-1155 balances for the listed token ids."""
        raise NotImplementedError(
            "get_chain_positions is not implemented yet -- pending: "
            "web3.eth.contract(ConditionalTokens).balanceOfBatch(...)"
        )

    def reconcile(self) -> PositionDrift:
        """Compare CLOB and chain views, return a ``PositionDrift`` report."""
        raise NotImplementedError(
            "reconcile is not implemented yet -- pending: union token_ids, "
            "fetch both, diff with tolerance, build PositionDrift"
        )
