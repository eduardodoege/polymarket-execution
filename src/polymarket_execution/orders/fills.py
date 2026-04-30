"""True fill price via ``client.get_trades`` (fixes a critical PnL bug).

The bug
-------
Polymarket executes orders **limit-or-better**: a sell limit @ $0.50 may
fill at $0.99 if the bid recovered between order send and match. Critically,
``client.get_order_status(order_id)`` returns the **limit price** in its
``price`` field, **not the fill price**.

Real-world consequence (caught in production 2026-04-29):

- Sent sell @ limit $0.020 (bid had collapsed momentarily)
- Bid recovered, real fill at $0.99
- Bot recorded LOSS $-4.84 (using limit) — true result was PROFIT +$0.47
- Bot tripped daily-loss limit and paused for 11h

The fix
-------
After confirming a fill, query ``client.get_trades(TradeParams(id=order_id))``
which returns each individual match with its **real** match price. Compute
the volume-weighted average price (VWAP) and use that for PnL.

Edge case: trades are not always indexed instantly (1-2s lag). If the
function returns ``None``, the caller should retry briefly before falling
back to the limit price.
"""

from __future__ import annotations

from typing import Any


def get_order_avg_fill_price(
    clob_client: Any,
    order_id: str,
) -> float | None:
    """Return the volume-weighted average fill price for ``order_id``.

    Returns ``None`` if the trades index has not caught up yet (caller should
    retry once or twice with a short delay before falling back to the limit price).
    """
    raise NotImplementedError(
        "v0.2.0: call client.get_trades(TradeParams(id=order_id)), "
        "return None if empty (lag), else compute sum(price*size) / sum(size)"
    )
