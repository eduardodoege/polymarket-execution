"""Trigger monitors: stop-loss and take-profit.

Both use the same underlying mechanic: monitor a reference price (or PnL),
fire an exit order when the trigger condition is crossed. The base class
``TriggerMonitor`` encapsulates the polling loop and exit dispatch;
concrete subclasses (``StopLossMonitor``, ``TakeProfitMonitor``) only
define the trigger predicate.
"""

from polymarket_execution.triggers.base import TriggerMonitor
from polymarket_execution.triggers.stop_loss import StopLossMonitor
from polymarket_execution.triggers.take_profit import TakeProfitMonitor

__all__ = ["TriggerMonitor", "StopLossMonitor", "TakeProfitMonitor"]
