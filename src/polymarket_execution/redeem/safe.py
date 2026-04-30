"""Gnosis Safe support for redeem operations.

Polymarket's ``signature_type=2`` (``POLY_GNOSIS_SAFE``) means user funds
are custodied in a Gnosis Safe, not the signer EOA. Operations that
modify on-chain state (redeem, wrap, allowance) must be routed through
``execTransaction`` on the Safe, signed by the EOA.

Reading state is unaffected: ``balanceOf(safe_address)`` works directly.
"""

from __future__ import annotations

from typing import Any


class SafeRedeemAdapter:
    """Adapter for executing redeem / wrap calls through a Gnosis Safe."""

    def __init__(
        self,
        web3_rpc_url: str,
        safe_address: str,
        signer_private_key: str,
    ) -> None:
        self.web3_rpc_url = web3_rpc_url
        self.safe_address = safe_address
        self.signer_private_key = signer_private_key

    def exec_via_safe(
        self,
        target_address: str,
        calldata: bytes,
        value: int = 0,
    ) -> str:
        """Execute ``calldata`` against ``target_address`` through the Safe.

        Returns the Safe execTransaction TX hash.
        """
        raise NotImplementedError(
            "v0.1.0: build Safe execTransaction, sign with EOA, submit to chain"
        )

    def is_owner(self) -> bool:
        """Check whether the configured signer EOA is an owner of the Safe."""
        raise NotImplementedError("v0.1.0: query Safe.getOwners() and check membership")

    def threshold(self) -> int:
        """Return the Safe's signature threshold (1 for single-owner Safes)."""
        raise NotImplementedError("v0.1.0: query Safe.getThreshold()")


# Silence unused-import warning
_ = Any
