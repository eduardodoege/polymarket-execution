"""Reference bot built on ``polymarket-execution``.

Currently minimal (v0.1.0): periodically discovers and redeems resolved
positions. Each library release expands this bot to demonstrate the new
modules — see ``README.md`` for the version map.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("example_bot")


def load_config(path: Path) -> dict[str, Any]:
    """Load the YAML config file."""
    import yaml

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def redeem_loop(config: dict[str, Any]) -> None:
    """Run an auto-redeem sweep every ``redeem_interval_s`` seconds.

    This is the v0.1.0 capability. v0.3+ will add stop-loss / take-profit
    loops and v0.4+ will add order placement.
    """
    from polymarket_execution.redeem import RedeemClient

    redeemer = RedeemClient(
        clob_client=None,  # construct your ClobClient and pass here
        web3_rpc_url=config["polygon_rpc_url"],
        safe_address=config.get("safe_address"),
        signer_private_key=config["private_key"],
    )

    interval = float(config.get("redeem_interval_s", 600))
    while True:
        try:
            result = redeemer.auto_redeem_all()
            logger.info(
                "Sweep done — redeemed=%d, wrapped=%.4f USDC.e",
                len(result.redeemed_markets),
                result.wrap_amount_usdc,
            )
        except Exception:
            logger.exception("Redeem sweep failed; will retry next interval")
        await asyncio.sleep(interval)


async def main_async(config_path: Path) -> int:
    config = load_config(config_path)
    logging.basicConfig(level=config.get("log_level", "INFO"))

    # v0.1.0: only the redeem loop runs. Add other loops as the library grows.
    await redeem_loop(config)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="example_bot — reference bot for polymarket-execution"
    )
    parser.add_argument("--config", type=Path, required=True, help="Path to config YAML")
    args = parser.parse_args()
    return asyncio.run(main_async(args.config))


if __name__ == "__main__":
    sys.exit(main())
