"""Custom exceptions for polymarket-execution.

Fail explicit: code that touches money raises specific exceptions, not generic ones.
"""


class PolymarketExecutionError(Exception):
    """Base exception for all polymarket-execution errors."""


# --- Order placement ---


class OrderPlacementError(PolymarketExecutionError):
    """Raised when an order cannot be placed (network, signing, validation)."""


class InsufficientBalanceError(PolymarketExecutionError):
    """Raised when balance/allowance is insufficient for the requested operation."""


class DustPositionError(PolymarketExecutionError):
    """Raised when attempting to act on a position below ``DUST_SHARES_THRESHOLD``."""


# --- Triggers (stop-loss / take-profit) ---


class TriggerError(PolymarketExecutionError):
    """Base for trigger monitor errors."""


class StopLossTriggerMissedError(TriggerError):
    """Stop-loss trigger fired but the exit order could not be placed in time."""


class TakeProfitTriggerMissedError(TriggerError):
    """Take-profit trigger fired but the exit order could not be placed in time."""


# --- Redeem ---


class RedeemError(PolymarketExecutionError):
    """Base for redeem errors."""


class WrapError(RedeemError):
    """Raised when ``CollateralOnramp.wrap`` (USDC.e -> pUSD) fails."""


# --- Recovery ---


class RecoveryError(PolymarketExecutionError):
    """Raised when recovery layers cannot determine the true state of a fill."""


# --- Price feed ---


class PriceFeedError(PolymarketExecutionError):
    """Raised when the price feed fails to deliver data."""


class PriceFeedDisconnectedError(PriceFeedError):
    """The WebSocket / data source is disconnected."""
