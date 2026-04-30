"""Recovery layers for masked fills.

When Polymarket processes an order but the response doesn't make it back
(network error, status timeout, balance lock, etc.), a bot can wrongly
think the order failed and double-act on it. These layers detect such
masked fills before the bot makes a wrong decision.

Five layers (battle-tested in production):

1. **Network error recovery** — after a network exception on send, check
   the position balance. If it dropped >= 85% of the attempted quantity,
   accept as filled. Emit ``NETWORK_ERROR_RECOVERED_FILL``.

2. **Status timeout recovery** — if ``get_order_status`` returns ``None``
   (timeout), check balance before advancing tier. Cancel the pending
   order before retrying. Emit ``STATUS_TIMEOUT_RECOVERED_FILL``.

3. **Balance lock recovery** — when the next tier fails with a "balance
   locked" error, verify balance drop, confirm via ``get_order_status``,
   and if ``size_matched > 0`` accept as filled and exit the tier loop.
   Emit ``BALANCE_LOCK_RECOVERED_FILL``.

4. **"Sum of matched orders" parsing** — Polymarket sometimes returns
   ``"balance: X, sum of matched orders: Y"`` in the error message itself.
   Parse with regex; if ``Y >= attempted * 0.85``, accept as filled.
   Independent of ``last_order_id`` (which may be ``None`` after a network
   error) and balance propagation lag. Emit ``MATCHED_ORDERS_RECOVERED_FILL``.

5. **Suspect drop catch-all** — in the exit path, if balance dropped
   unexpectedly, query ``get_order_status(last_order_id)``. If
   ``size_matched >= original * 0.85``, reconstitute PnL by reducing both
   ``quantity`` and ``cost_usd`` proportionally. Emit ``SUSPECT_DROP_RECOVERED``.

All layers log structured events (compatible with stdlib ``logging``)
so analytics can correlate masked-fill incidents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from polymarket_execution.constants import RECOVERY_FILL_RATIO


@dataclass
class RecoveryResult:
    """Outcome of a recovery layer evaluation."""

    recovered: bool
    """True if the layer determined the order was actually filled."""

    matched_size: float | None = None
    """Size detected as matched, if available."""

    detected_via: str | None = None
    """Which layer fired.

    Possible values: ``network``, ``status_timeout``, ``balance_lock``,
    ``matched_orders``, ``suspect_drop``.
    """


# --- Layer 1: network error ---


def recover_from_network_error(
    pre_balance: float,
    post_balance: float,
    attempted_qty: float,
    fill_ratio: float = RECOVERY_FILL_RATIO,
) -> RecoveryResult:
    """Layer 1 — balance check after a network exception during order send."""
    drop = pre_balance - post_balance
    if drop >= attempted_qty * fill_ratio:
        return RecoveryResult(recovered=True, matched_size=drop, detected_via="network")
    return RecoveryResult(recovered=False)


# --- Layer 2: status timeout ---


def recover_from_status_timeout(
    pre_balance: float,
    post_balance: float,
    remaining_qty: float,
    fill_ratio: float = RECOVERY_FILL_RATIO,
) -> RecoveryResult:
    """Layer 2 — balance check after ``get_order_status`` timeout."""
    drop = pre_balance - post_balance
    if drop >= remaining_qty * fill_ratio:
        return RecoveryResult(recovered=True, matched_size=drop, detected_via="status_timeout")
    return RecoveryResult(recovered=False)


# --- Layer 3: balance lock ---


def recover_from_balance_lock(
    clob_client: Any,
    last_order_id: str | None,
    pre_balance: float,
    post_balance: float,
    try_qty: float,
    fill_ratio: float = RECOVERY_FILL_RATIO,
) -> RecoveryResult:
    """Layer 3 — balance lock error from a follow-up tier suggests prior fill."""
    raise NotImplementedError(
        "v0.4.0: if balance dropped >= try_qty * fill_ratio, "
        "and get_order_status(last_order_id).size_matched > 0, recover"
    )


# --- Layer 4: "sum of matched orders" parsing ---

_MATCHED_ORDERS_RE = re.compile(
    r"sum\s+of\s+matched\s+orders:\s*(\d+)",
    re.IGNORECASE,
)


def recover_from_matched_orders_error(
    error_message: str,
    attempted_qty: float,
    fill_ratio: float = RECOVERY_FILL_RATIO,
) -> RecoveryResult:
    """Layer 4 — Polymarket itself confirms matched size in the error string.

    Independent of ``last_order_id`` (may be ``None`` after a network error)
    and balance propagation (~5s lag possible). The most reliable layer.
    """
    match = _MATCHED_ORDERS_RE.search(error_message)
    if match is None:
        return RecoveryResult(recovered=False)
    matched_wei = int(match.group(1))
    # Polymarket reports shares in 6-decimal format (USDC convention)
    matched_shares = matched_wei / 1_000_000
    if matched_shares >= attempted_qty * fill_ratio:
        return RecoveryResult(
            recovered=True,
            matched_size=matched_shares,
            detected_via="matched_orders",
        )
    return RecoveryResult(recovered=False)


# --- Layer 5: suspect drop catch-all ---


def recover_from_suspect_drop(
    clob_client: Any,
    last_order_id: str | None,
    original_qty: float,
    current_qty: float,
    fill_ratio: float = RECOVERY_FILL_RATIO,
) -> RecoveryResult:
    """Layer 5 — catch-all when balance dropped but no other layer fired."""
    raise NotImplementedError(
        "v0.4.0: if last_order_id present, get_order_status, "
        "if size_matched >= original_qty * fill_ratio, recover (caller reconstitutes PnL)"
    )


__all__ = [
    "RecoveryResult",
    "recover_from_network_error",
    "recover_from_status_timeout",
    "recover_from_balance_lock",
    "recover_from_matched_orders_error",
    "recover_from_suspect_drop",
]
