"""Gnosis Safe wallet support.

Polymarket users typically operate via Gnosis Safe (``signature_type=2`` /
``POLY_GNOSIS_SAFE``). The underlying ``polymarket_apis.PolymarketWeb3Client``
handles this transparently when constructed with ``signature_type=2``: it
routes state-changing calls through ``execTransaction`` on the Safe, signed
by the EOA private key.

For EOA-only mode, pass ``signature_type=0`` to ``RedeemClient``.

This module is intentionally thin — Safe support is built into the
underlying client, not implemented here. ``SafeRedeemAdapter`` is a
placeholder for future Safe-specific helpers (owner inspection, threshold
queries, etc.).
"""

from __future__ import annotations

from typing import Any


class SafeRedeemAdapter:
    """Placeholder for Safe-specific introspection helpers.

    Construction is **not required** to use Safe wallets — pass
    ``signature_type=2`` to ``RedeemClient`` and Safe routing happens
    automatically via the underlying ``polymarket-apis`` client.

    Future versions will add owner/threshold inspection on top of an
    existing ``web3_client``.
    """

    def __init__(self, web3_client: Any) -> None:
        self.web3_client = web3_client

    @property
    def safe_address(self) -> str:
        """Address of the Safe (== ``web3_client.address`` for ``signature_type=2``)."""
        return str(self.web3_client.address)

    def is_owner(self) -> bool:
        """Check whether the configured EOA is an owner of the Safe."""
        raise NotImplementedError("v0.2.0+: query Safe.getOwners() and check membership")

    def threshold(self) -> int:
        """Return the Safe's signature threshold (1 for single-owner Safes)."""
        raise NotImplementedError("v0.2.0+: query Safe.getThreshold()")
