"""Public constants — Polymarket CLOB v2 contract addresses, gas estimates, and protocol limits."""

from typing import Final

# Polygon mainnet contract addresses (CLOB v2)
USDCE_ADDRESS: Final[str] = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
PUSD_ADDRESS: Final[str] = "0xC011a73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F"
COLLATERAL_ONRAMP_ADDRESS: Final[str] = "0x93070a847efEf7F70739046A929D47a521F5B8ee"

# Polymarket protocol limits (validated against production)
DUST_SHARES_THRESHOLD: Final[float] = 1.0
"""Below this share count, Polymarket rejects sells with 'invalid amounts'.

Reason: shares × price rounds to 0 USDC wei. Defense-in-depth:
positions below threshold should not trigger guards.
"""

MIN_STAKE_USD: Final[float] = 5.0
"""Minimum viable stake on Polymarket CLOB.

Below this, the order book rejects sells by minimum order size. Mitigation
for drawdown is to pause the strategy, not reduce stake further.
"""

# Recovery layer thresholds (see polymarket_execution.recovery)
RECOVERY_FILL_RATIO: Final[float] = 0.85
"""If balance dropped >= this fraction of attempted quantity, treat as filled."""

# Wrap operation gas estimate (CollateralOnramp.wrap)
WRAP_GAS_ESTIMATE: Final[int] = 131_232
"""Approximate gas cost of CollateralOnramp.wrap (USDC.e -> pUSD)."""

# ChainLink RTDS WebSocket endpoint
CHAINLINK_RTDS_WS_URL: Final[str] = "wss://ws-live-data.polymarket.com"
CHAINLINK_RTDS_TOPIC: Final[str] = "crypto_prices_chainlink"
