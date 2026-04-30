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
"""

from __future__ import annotations

import io
import logging
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Any

from polymarket_execution.constants import COLLATERAL_ONRAMP_ADDRESS, USDCE_ADDRESS
from polymarket_execution.exceptions import WrapError

logger = logging.getLogger(__name__)


# Minimal ABI: just the wrap function we call.
ONRAMP_WRAP_ABI = [
    {
        "name": "wrap",
        "type": "function",
        "inputs": [
            {"name": "_asset", "type": "address"},
            {"name": "_to", "type": "address"},
            {"name": "_amount", "type": "uint256"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    }
]


@dataclass
class WrapReceipt:
    """Outcome of a USDC.e -> pUSD wrap call."""

    tx_hash: str | None
    amount_usdc: float
    gas_used: int = 0
    gas_cost_pol: float = 0.0


def wrap_usdce_to_pusd(web3_client: Any) -> WrapReceipt | None:
    """Wrap the wallet's full USDC.e balance to pUSD via CollateralOnramp.

    ``web3_client`` must be a ``polymarket_apis.PolymarketWeb3Client`` instance.
    The Safe-vs-EOA distinction is handled internally by the client based on
    its configured ``signature_type``.

    Returns ``None`` immediately if the USDC.e balance is zero (idempotent).
    Returns a ``WrapReceipt`` on success.
    Raises ``WrapError`` if the transaction was submitted but reverted; the
    caller decides whether to swallow this (it does not invalidate prior
    redeems).
    """
    from web3 import Web3

    usdce_addr = Web3.to_checksum_address(USDCE_ADDRESS)
    onramp_addr = Web3.to_checksum_address(COLLATERAL_ONRAMP_ADDRESS)

    usdce = web3_client.w3.eth.contract(address=usdce_addr, abi=web3_client.usdc_abi)
    balance_wei = int(usdce.functions.balanceOf(web3_client.address).call())

    if balance_wei == 0:
        logger.debug("USDC.e balance is zero, skipping wrap")
        return None

    balance_usdc = balance_wei / 1e6
    logger.info("Wrapping %.4f USDC.e -> pUSD via CollateralOnramp", balance_usdc)

    onramp = web3_client.w3.eth.contract(address=onramp_addr, abi=ONRAMP_WRAP_ABI)
    wrap_data = onramp.encode_abi(
        abi_element_identifier="wrap",
        args=[usdce_addr, web3_client.address, balance_wei],
    )

    captured = io.StringIO()
    with redirect_stdout(captured):
        receipt = web3_client._execute(
            onramp_addr, wrap_data, "Wrap USDC.e -> pUSD", metadata="wrap"
        )

    if receipt is None or getattr(receipt, "status", 0) != 1:
        status = getattr(receipt, "status", "no receipt") if receipt is not None else "no receipt"
        raise WrapError(f"Wrap transaction failed: status={status}")

    tx_hash = _extract_tx_hash(receipt)
    gas_used = int(getattr(receipt, "gas_used", 0) or 0)
    gas_price = int(getattr(receipt, "effective_gas_price", 0) or 0)
    gas_cost_pol = (gas_used * gas_price) / 1e18 if gas_used and gas_price else 0.0

    short_hash = tx_hash[:20] if tx_hash else "?"
    logger.info(
        "Wrap ok | tx=%s | %.4f USDC.e -> pUSD | gas=%d (%.6f POL)",
        short_hash,
        balance_usdc,
        gas_used,
        gas_cost_pol,
    )

    return WrapReceipt(
        tx_hash=tx_hash,
        amount_usdc=balance_usdc,
        gas_used=gas_used,
        gas_cost_pol=gas_cost_pol,
    )


def _extract_tx_hash(receipt: Any) -> str | None:
    """Extract a hex tx hash from a receipt object (various attribute names)."""
    for attr in ("transaction_hash", "tx_hash", "transactionHash"):
        value = getattr(receipt, attr, None)
        if value is None:
            continue
        if hasattr(value, "hex"):
            return str(value.hex())
        return str(value)
    return None
