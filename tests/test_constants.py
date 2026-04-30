"""Smoke tests for public constants."""

from polymarket_execution import constants


def test_dust_threshold_is_one_share():
    assert constants.DUST_SHARES_THRESHOLD == 1.0


def test_min_stake_is_five_dollars():
    assert constants.MIN_STAKE_USD == 5.0


def test_recovery_fill_ratio_in_range():
    assert 0.5 < constants.RECOVERY_FILL_RATIO < 1.0


def test_addresses_are_checksum_format():
    """All Polygon addresses should be 42-char hex (0x + 40)."""
    for addr in (
        constants.USDCE_ADDRESS,
        constants.PUSD_ADDRESS,
        constants.COLLATERAL_ONRAMP_ADDRESS,
    ):
        assert addr.startswith("0x")
        assert len(addr) == 42


def test_chainlink_rtds_url_is_wss():
    assert constants.CHAINLINK_RTDS_WS_URL.startswith("wss://")
