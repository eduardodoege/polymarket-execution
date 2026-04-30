"""Core redeem logic — discover resolved positions, claim winnings, wrap proceeds.

Designed for both EOA wallets and Gnosis Safes (``signature_type=2`` is the
default for Polymarket users). Built on top of
``polymarket_apis.PolymarketWeb3Client``.

Workflow
--------
1. ``discover_redeemable()`` queries the Polymarket Data API for positions
   in resolved markets that have unredeemed shares.
2. For each market, ``redeem_market()`` calls
   ``ConditionalTokens.redeemPositions(...)`` (via the underlying client).
3. After the loop, ``auto_redeem_all()`` calls ``wrap_usdce_to_pusd``
   once (idempotent — no-op if USDC.e balance is zero) so the proceeds
   become readable to V2 collateral views.

Why the wrap step matters (CLOB v2)
-----------------------------------
``polymarket-apis`` redeem still pays winnings in USDC.e (the V1
collateral token). After the V2 cutover (2026-04-28) the bot reads its
balance via ``AssetType.COLLATERAL`` which now means **pUSD**, not USDC.e.
Without wrap, redeemed USDC.e sits idle in the wallet/Safe and the bot's
balance view does not reflect it.
"""

from __future__ import annotations

import io
import logging
import time
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any

import httpx

from polymarket_execution.constants import (
    DEFAULT_POLYGON_RPC_URLS,
    POLYMARKET_DATA_API_URL,
)
from polymarket_execution.exceptions import RedeemError
from polymarket_execution.redeem.wrap import WrapReceipt, wrap_usdce_to_pusd

logger = logging.getLogger(__name__)


@dataclass
class RedeemablePosition:
    """A position with redeemable shares from a resolved market."""

    condition_id: str
    size: float
    value: float
    outcome: str

    @classmethod
    def from_data_api(cls, payload: dict[str, Any]) -> RedeemablePosition:
        """Construct from a Polymarket Data API ``/positions`` row."""
        return cls(
            condition_id=str(payload.get("conditionId", payload.get("condition_id", ""))),
            size=float(payload.get("size", 0) or 0),
            value=float(payload.get("currentValue", payload.get("value", 0)) or 0),
            outcome=str(payload.get("outcome", "?")),
        )


@dataclass
class RedeemReceipt:
    """Outcome of a single ``redeemPositions`` transaction."""

    condition_id: str
    success: bool
    tx_hash: str | None = None
    gas_used: int = 0
    gas_cost_pol: float = 0.0
    error: str | None = None


@dataclass
class RedeemResult:
    """Summary of an ``auto_redeem_all`` sweep."""

    redeemed_markets: list[str] = field(default_factory=list)
    failed_markets: list[tuple[str, str]] = field(default_factory=list)
    redeem_tx_hashes: list[str] = field(default_factory=list)
    wrap_receipt: WrapReceipt | None = None
    total_gas_used: int = 0
    total_gas_cost_pol: float = 0.0

    @property
    def wrap_tx_hash(self) -> str | None:
        """TX hash of the post-redeem wrap, if it ran. ``None`` otherwise."""
        return self.wrap_receipt.tx_hash if self.wrap_receipt is not None else None

    @property
    def wrap_amount_usdc(self) -> float:
        """Amount of USDC.e wrapped to pUSD. ``0.0`` if wrap did not run."""
        return self.wrap_receipt.amount_usdc if self.wrap_receipt is not None else 0.0


class RedeemClient:
    """Discover, redeem, and wrap winnings from resolved Polymarket positions.

    Designed for both EOA wallets and Gnosis Safes. Built on top of
    ``polymarket_apis.PolymarketWeb3Client`` (constructed lazily on first
    use). Pass ``web3_client=`` to inject a pre-configured client (useful
    for tests or to share a client across multiple operations).

    Parameters
    ----------
    private_key:
        EOA private key (hex string). Required unless ``web3_client`` is
        injected.
    rpc_url:
        Preferred Polygon RPC. If ``None``, uses the first endpoint from
        ``DEFAULT_POLYGON_RPC_URLS``. The full list is used as a fallback
        chain on RPC errors.
    signature_type:
        ``0`` for EOA, ``2`` for Gnosis Safe (Polymarket default).
    chain_id:
        Polygon mainnet is ``137``.
    http_client:
        Reusable ``httpx.Client``. If ``None``, one is created and closed
        on ``close()``.
    data_api_url:
        Polymarket Data API base URL.
    size_threshold:
        Filter for ``/positions`` query — positions with shares <=
        threshold are skipped.
    wrap_after_redeem:
        Whether to call ``wrap_usdce_to_pusd`` after a successful sweep.
        Set to ``False`` only if you handle the wrap yourself.
    rpc_fallback_urls:
        Override the default fallback chain.
    proxy_url:
        Optional SOCKS5/HTTP proxy URL passed to both the HTTP client and
        the underlying Web3 client.
    web3_client:
        Inject a pre-built ``PolymarketWeb3Client``. Skips internal
        construction (and the lazy import).
    """

    def __init__(
        self,
        private_key: str | None = None,
        *,
        rpc_url: str | None = None,
        signature_type: int = 2,
        chain_id: int = 137,
        http_client: httpx.Client | None = None,
        data_api_url: str = POLYMARKET_DATA_API_URL,
        size_threshold: float = 0.01,
        wrap_after_redeem: bool = True,
        rpc_fallback_urls: tuple[str, ...] | list[str] | None = None,
        proxy_url: str | None = None,
        web3_client: Any | None = None,
    ) -> None:
        if web3_client is None and private_key is None:
            raise ValueError("Either private_key or web3_client must be provided")

        self.private_key = private_key
        self.signature_type = signature_type
        self.chain_id = chain_id
        self.data_api_url = data_api_url.rstrip("/")
        self.size_threshold = size_threshold
        self.wrap_after_redeem = wrap_after_redeem
        self._proxy_url = proxy_url
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(timeout=30.0, proxy=proxy_url)

        endpoints = list(rpc_fallback_urls) if rpc_fallback_urls else list(DEFAULT_POLYGON_RPC_URLS)
        if rpc_url is not None:
            endpoints = [rpc_url] + [u for u in endpoints if u != rpc_url]
        self._rpc_endpoints: list[str] = endpoints

        self._rpc_index = 0
        self._web3_client: Any | None = web3_client
        self._redeemed_conditions: set[str] = set()
        self.total_gas_used = 0
        self.total_gas_cost_pol = 0.0

    @property
    def web3_client(self) -> Any:
        """Lazy-initialize the underlying ``PolymarketWeb3Client``."""
        if self._web3_client is None:
            self._init_web3_client(self._rpc_endpoints[self._rpc_index])
        return self._web3_client

    @property
    def wallet_address(self) -> str:
        """Address that holds positions (Safe address for ``signature_type=2``)."""
        return str(self.web3_client.address)

    def _init_web3_client(self, rpc_url: str) -> None:
        try:
            from polymarket_apis import PolymarketWeb3Client
        except ImportError as e:  # pragma: no cover - import guard
            raise RedeemError(
                "polymarket-apis is required for RedeemClient; "
                "reinstall polymarket-execution with: pip install --upgrade polymarket-execution"
            ) from e

        if self.private_key is None:
            raise RedeemError("Cannot lazy-init web3 client without private_key")

        client = PolymarketWeb3Client(
            private_key=self.private_key,
            signature_type=self.signature_type,
            chain_id=self.chain_id,
            rpc_url=rpc_url,
        )
        if self._proxy_url:
            client.client = httpx.Client(http2=True, timeout=30.0, proxy=self._proxy_url)
        self._web3_client = client
        logger.info(
            "PolymarketWeb3Client initialized | rpc=%s | address=%s...",
            rpc_url,
            client.address[:15],
        )

    def _try_next_rpc(self) -> bool:
        """Switch to the next fallback RPC. Returns ``False`` when exhausted."""
        self._web3_client = None
        self._rpc_index += 1
        if self._rpc_index >= len(self._rpc_endpoints):
            self._rpc_index = 0
            return False
        rpc_url = self._rpc_endpoints[self._rpc_index]
        try:
            self._init_web3_client(rpc_url)
            logger.warning("Switched to fallback RPC: %s", rpc_url)
            return True
        except Exception as e:  # noqa: BLE001 - swallow init failure, try next
            logger.warning("RPC %s failed init: %s", rpc_url, e)
            return self._try_next_rpc()

    def discover_redeemable(self) -> list[RedeemablePosition]:
        """Return resolved positions with redeemable shares for the configured wallet.

        Skips positions already redeemed in this session (deduplicated by
        ``condition_id``) and empty positions (``size == 0 and value == 0``).
        """
        address = self.wallet_address
        try:
            response = self._http_client.get(
                f"{self.data_api_url}/positions",
                params={
                    "user": address,
                    "redeemable": "true",
                    "sizeThreshold": str(self.size_threshold),
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RedeemError(f"Data API request failed: {e}") from e

        data = response.json()
        positions = data if isinstance(data, list) else data.get("positions", [])

        result: list[RedeemablePosition] = []
        for raw in positions:
            pos = RedeemablePosition.from_data_api(raw)
            if not pos.condition_id or pos.condition_id in self._redeemed_conditions:
                continue
            if pos.size <= 0 and pos.value <= 0:
                # Empty/already-redeemed — mark to skip on next discovery.
                self._redeemed_conditions.add(pos.condition_id)
                continue
            result.append(pos)
            logger.info(
                "Found redeemable: %.2f shares (~$%.2f) (%s) | %s...",
                pos.size,
                pos.value,
                pos.outcome,
                pos.condition_id[:25],
            )
        return result

    def redeem_market(
        self,
        condition_id: str,
        yes_shares: float,
        no_shares: float,
        *,
        neg_risk: bool = False,
        max_attempts: int = 3,
    ) -> RedeemReceipt:
        """Redeem a single market via on-chain ``ConditionalTokens.redeemPositions``.

        Retries automatically on RPC-level errors (rate limit, gateway,
        connection) by switching through the configured fallback chain. Does
        NOT retry on protocol errors like ``execution reverted`` or nonce
        issues — those require a future session.
        """
        if not condition_id.startswith("0x"):
            condition_id = "0x" + condition_id

        last_error: str | None = None
        for attempt in range(max_attempts):
            try:
                logger.info(
                    "Redeeming %s... (yes=%.2f, no=%.2f, neg_risk=%s)",
                    condition_id[:25],
                    yes_shares,
                    no_shares,
                    neg_risk,
                )
                # polymarket-apis prints to stdout; capture so library
                # logging stays clean.
                captured = io.StringIO()
                with redirect_stdout(captured):
                    receipt = self.web3_client.redeem_position(
                        condition_id=condition_id,
                        amounts=[yes_shares, no_shares],
                        neg_risk=neg_risk,
                    )

                if receipt is None:
                    logger.info("Redeem submitted (no receipt available)")
                    self._redeemed_conditions.add(condition_id)
                    return RedeemReceipt(condition_id=condition_id, success=True)

                if int(getattr(receipt, "status", 0)) != 1:
                    last_error = f"tx status {receipt.status}"
                    logger.warning("Redeem TX failed: status=%s", receipt.status)
                    self._redeemed_conditions.add(condition_id)
                    return RedeemReceipt(condition_id=condition_id, success=False, error=last_error)

                tx_hash = _extract_tx_hash(receipt)
                gas_used = int(
                    getattr(receipt, "gas_used", 0) or getattr(receipt, "gasUsed", 0) or 0
                )
                gas_price = int(
                    getattr(receipt, "effective_gas_price", 0)
                    or getattr(receipt, "effectiveGasPrice", 0)
                    or 0
                )
                gas_cost_pol = (gas_used * gas_price) / 1e18 if gas_used and gas_price else 0.0

                self.total_gas_used += gas_used
                self.total_gas_cost_pol += gas_cost_pol
                self._redeemed_conditions.add(condition_id)

                short_hash = tx_hash[:20] if tx_hash else "?"
                logger.info(
                    "Redeem ok | tx=%s... | gas=%d (%.6f POL)",
                    short_hash,
                    gas_used,
                    gas_cost_pol,
                )
                return RedeemReceipt(
                    condition_id=condition_id,
                    success=True,
                    tx_hash=tx_hash,
                    gas_used=gas_used,
                    gas_cost_pol=gas_cost_pol,
                )
            except Exception as e:  # noqa: BLE001 - classify by message below
                msg_lower = str(e).lower()
                last_error = str(e)

                if "execution reverted" in msg_lower or "already" in msg_lower:
                    # Likely already redeemed; treat as success and stop.
                    logger.info(
                        "Redeem reverted (likely already redeemed): %s...", condition_id[:25]
                    )
                    self._redeemed_conditions.add(condition_id)
                    return RedeemReceipt(
                        condition_id=condition_id, success=True, error="already redeemed"
                    )

                if "nonce" in msg_lower:
                    # Nonce errors usually mean the TX never landed; let the
                    # next session retry (do NOT mark as redeemed).
                    logger.warning("Nonce issue, will retry next session: %s", e)
                    return RedeemReceipt(
                        condition_id=condition_id,
                        success=False,
                        error=f"nonce issue: {e}",
                    )

                if any(
                    code in str(e)
                    for code in (
                        "400",
                        "429",
                        "503",
                        "Bad Request",
                        "Too Many",
                        "Service Unavailable",
                        "ConnectionError",
                        "ConnectError",
                    )
                ):
                    # RPC-level error — try next fallback.
                    logger.warning(
                        "RPC error (attempt %d/%d): %s",
                        attempt + 1,
                        max_attempts,
                        str(e)[:80],
                    )
                    if attempt < max_attempts - 1 and self._try_next_rpc():
                        continue
                    return RedeemReceipt(
                        condition_id=condition_id,
                        success=False,
                        error=f"RPC exhausted: {e}",
                    )

                # Unknown error — fail without retry.
                logger.error("Redeem failed: %s", e)
                return RedeemReceipt(condition_id=condition_id, success=False, error=last_error)

        return RedeemReceipt(
            condition_id=condition_id,
            success=False,
            error=last_error or "max attempts reached",
        )

    def auto_redeem_all(self, sleep_between_s: float = 2.0) -> RedeemResult:
        """Discover and redeem all eligible positions, then wrap USDC.e to pUSD.

        Idempotent and best-effort: failures on individual markets do not
        stop the sweep. The wrap step is attempted once at the end if any
        market was successfully redeemed (no-op when USDC.e balance is 0).
        """
        result = RedeemResult()

        try:
            redeemable = self.discover_redeemable()
        except RedeemError as e:
            logger.error("Discovery failed: %s", e)
            return result

        if not redeemable:
            logger.info("No redeemable positions found")
            return result

        for pos in redeemable:
            yes_shares, no_shares = self._split_shares(pos)
            receipt = self.redeem_market(
                condition_id=pos.condition_id,
                yes_shares=yes_shares,
                no_shares=no_shares,
            )
            if receipt.success:
                result.redeemed_markets.append(pos.condition_id)
                if receipt.tx_hash:
                    result.redeem_tx_hashes.append(receipt.tx_hash)
            else:
                result.failed_markets.append((pos.condition_id, receipt.error or "unknown"))
            if sleep_between_s > 0:
                time.sleep(sleep_between_s)

        result.total_gas_used = self.total_gas_used
        result.total_gas_cost_pol = self.total_gas_cost_pol

        if self.wrap_after_redeem and result.redeemed_markets:
            try:
                wrap = wrap_usdce_to_pusd(self.web3_client)
                result.wrap_receipt = wrap
                if wrap is not None and wrap.gas_used:
                    result.total_gas_used += wrap.gas_used
                    result.total_gas_cost_pol += wrap.gas_cost_pol
            except Exception as e:  # noqa: BLE001 - wrap is best-effort
                logger.warning("Wrap failed (non-fatal, USDC.e stays in wallet): %s", e)

        logger.info(
            "Sweep complete: %d redeemed, %d failed",
            len(result.redeemed_markets),
            len(result.failed_markets),
        )
        return result

    @staticmethod
    def _split_shares(pos: RedeemablePosition) -> tuple[float, float]:
        """Split position size into ``(yes_shares, no_shares)`` based on outcome."""
        outcome = pos.outcome.upper()
        if outcome == "YES":
            return (pos.size, 0.0)
        if outcome == "NO":
            return (0.0, pos.size)
        # Unknown outcome — pass both; the contract handles which is valid.
        return (pos.size, pos.size)

    def close(self) -> None:
        """Close the HTTP client if owned by this instance."""
        if self._owns_http_client:
            self._http_client.close()

    def __enter__(self) -> RedeemClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


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
