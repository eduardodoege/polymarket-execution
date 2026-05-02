"""Order lifecycle management — retry, replace, stale detection.

Production trading needs more than "place order, hope". This module
handles the lifecycle once an order is live:

- **Retry policy**: pluggable backoff for transient failures (network,
  signing, rate limit). Use ``orders.place`` for the first attempt; this
  module wraps for retries.
- **Stale detection**: an order that's been sitting at the top of the
  book for too long without a fill is probably mispriced. Detect and act.
- **Replacement**: cancel-and-replace as one logical operation, with
  rollback if the cancel succeeds but the replace fails.

What this module is NOT
-----------------------
This is plumbing for *executing* lifecycle decisions. It does not decide
*when* to retry or *when* to consider an order stale — those are policy
choices for the caller. We provide the mechanics, you provide the rules.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class RetryPolicy:
    """Configuration for retry-with-backoff."""

    max_attempts: int = 3
    initial_delay_s: float = 0.5
    backoff_factor: float = 2.0
    max_delay_s: float = 5.0


def retry_with_backoff(
    fn: Callable[[], Any],
    policy: RetryPolicy | None = None,
    is_retryable: Callable[[Exception], bool] | None = None,
) -> Any:
    """Run ``fn`` with retry-on-exception governed by ``policy``."""
    if policy is None:
        policy = RetryPolicy()
    raise NotImplementedError(
        "retry_with_backoff is not implemented yet -- pending: try/except "
        "loop, exponential backoff, classify retryability via is_retryable hook"
    )


@dataclass
class StaleOrderSpec:
    """Spec for stale-order detection."""

    order_id: str
    placed_at_ts: float
    max_age_s: float


class StaleOrderDetector:
    """Track open orders and flag those exceeding ``max_age_s``."""

    def __init__(self, clob_client: Any) -> None:
        self.clob_client = clob_client
        self._tracked: dict[str, StaleOrderSpec] = {}

    def track(self, spec: StaleOrderSpec) -> None:
        """Begin tracking ``spec``."""
        self._tracked[spec.order_id] = spec

    def list_stale(self, now_ts: float) -> list[StaleOrderSpec]:
        """Return tracked orders whose age exceeds their ``max_age_s``."""
        raise NotImplementedError(
            "list_stale is not implemented yet -- pending: filter _tracked by "
            "(now - placed_at) > max_age, also verify still open via get_order"
        )


def cancel_and_replace(
    clob_client: Any,
    order_id: str,
    new_price: float,
    new_size: float | None = None,
) -> Any:
    """Cancel ``order_id`` and place a replacement at ``new_price``.

    If cancel succeeds but replace fails, raises with the cancel TX info
    so the caller can recover (the order is gone, but no new order is live).
    """
    raise NotImplementedError(
        "cancel_and_replace is not implemented yet -- pending: cancel via "
        "OrderPayload, await confirmation, then place new order"
    )
