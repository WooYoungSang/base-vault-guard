"""Real data collection from free APIs for Vault Guard ML training."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFILLAMA_BASE = "https://api.llama.fi"
DEFILLAMA_YIELDS = "https://yields.llama.fi"

BASE_RPC_URL = "https://mainnet.base.org"

# Protocols we care about on Base (names match DeFiLlama project field)
TARGET_PROTOCOLS = [
    "aave-v3", "compound-v3",
    "morpho-v1",
    "aerodrome-v1", "aerodrome-slipstream",
]

# Mapping from yields pool project name -> protocol API slug for TVL history
# (The yields endpoint and protocol endpoint use different naming)
PROTOCOL_API_SLUG: dict[str, str] = {
    "aave-v3": "aave-v3",
    "compound-v3": "compound-v3",
    "morpho-v1": "morpho",
    "aerodrome-v1": "aerodrome",
    "aerodrome-slipstream": "aerodrome-slipstream",
}

# Rate limiting
_DEFILLAMA_MIN_INTERVAL = 0.5  # 2 req/s max
_RPC_MIN_INTERVAL = 0.2  # 5 req/s max

# ---------------------------------------------------------------------------
# Audit registry (static, well-known protocols)
# ---------------------------------------------------------------------------

AUDIT_REGISTRY: dict[str, dict] = {
    "aave-v3": {
        "auditors": ["OpenZeppelin", "Trail of Bits"],
        "score": 0.95,
    },
    "compound-v3": {
        "auditors": ["OpenZeppelin"],
        "score": 0.90,
    },
    "morpho-v1": {
        "auditors": ["Spearbit"],
        "score": 0.90,
    },
    "aerodrome-v1": {
        "auditors": ["Code4rena"],
        "score": 0.85,
    },
    "aerodrome-slipstream": {
        "auditors": ["Code4rena"],
        "score": 0.85,
    },
}

DEFAULT_AUDIT_SCORE = 0.3


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PoolData:
    """Raw pool data from DeFiLlama."""

    pool_id: str
    chain: str
    project: str
    symbol: str
    tvl_usd: float
    apy: float | None
    apy_base: float | None
    apy_reward: float | None
    pool_meta: str | None = None


@dataclass
class ProtocolTVLHistory:
    """TVL history for a protocol on Base."""

    protocol: str
    # list of (timestamp, tvl_usd) tuples sorted by time
    history: list[tuple[int, float]] = field(default_factory=list)


@dataclass
class CollectedVault:
    """Aggregated vault data from all sources."""

    pool_id: str
    protocol: str
    symbol: str
    tvl_usd: float
    apy: float
    audit_score: float
    audit_info: str
    tvl_history: list[tuple[int, float]] = field(default_factory=list)
    utilization: float | None = None
    oracle_price: float | None = None


# ---------------------------------------------------------------------------
# Rate-limited HTTP helpers
# ---------------------------------------------------------------------------


class RateLimiter:
    """Simple token-bucket style rate limiter."""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._last_call = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()


# ---------------------------------------------------------------------------
# DeFiLlama collector
# ---------------------------------------------------------------------------


class DeFiLlamaCollector:
    """Collects TVL and APY data from DeFiLlama free API."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None
        self._limiter = RateLimiter(_DEFILLAMA_MIN_INTERVAL)

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
            self._owns_client = True
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, url: str) -> dict | list | None:
        """Rate-limited GET with retry."""
        client = await self._ensure_client()
        for attempt in range(3):
            await self._limiter.wait()
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning("DeFiLlama request failed (attempt %d): %s", attempt + 1, exc)
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        return None

    async def get_base_pools(self) -> list[PoolData]:
        """Fetch all yield pools on Base chain."""
        data = await self._get(f"{DEFILLAMA_YIELDS}/pools")
        if not data or not isinstance(data, dict):
            return []

        pools_raw = data.get("data", [])
        results: list[PoolData] = []

        for p in pools_raw:
            if p.get("chain", "").lower() != "base":
                continue
            project = p.get("project", "").lower()
            if project not in TARGET_PROTOCOLS:
                continue

            results.append(PoolData(
                pool_id=p.get("pool", ""),
                chain="Base",
                project=project,
                symbol=p.get("symbol", ""),
                tvl_usd=float(p.get("tvlUsd", 0)),
                apy=p.get("apy"),
                apy_base=p.get("apyBase"),
                apy_reward=p.get("apyReward"),
                pool_meta=p.get("poolMeta"),
            ))

        logger.info("Found %d Base pools from target protocols", len(results))
        return results

    async def get_protocol_tvl_history(self, protocol: str) -> ProtocolTVLHistory:
        """Fetch historical TVL for a protocol."""
        data = await self._get(f"{DEFILLAMA_BASE}/protocol/{protocol}")
        if not data or not isinstance(data, dict):
            return ProtocolTVLHistory(protocol=protocol)

        # Extract chain-specific TVL from chainTvls
        chain_tvls = data.get("chainTvls", {})
        base_tvl = chain_tvls.get("Base", {}).get("tvl", [])

        history: list[tuple[int, float]] = []
        for entry in base_tvl:
            ts = entry.get("date", 0)
            tvl = entry.get("totalLiquidityUSD", 0.0)
            if ts and tvl:
                history.append((int(ts), float(tvl)))

        history.sort(key=lambda x: x[0])
        logger.info("Protocol %s: %d TVL history points on Base", protocol, len(history))
        return ProtocolTVLHistory(protocol=protocol, history=history)

    async def get_base_chain_tvl(self) -> list[tuple[int, float]]:
        """Fetch Base chain total TVL history."""
        data = await self._get(f"{DEFILLAMA_BASE}/v2/historicalChainTvl/Base")
        if not data or not isinstance(data, list):
            return []

        history: list[tuple[int, float]] = []
        for entry in data:
            ts = entry.get("date", 0)
            tvl = entry.get("tvl", 0.0)
            if ts and tvl:
                history.append((int(ts), float(tvl)))

        history.sort(key=lambda x: x[0])
        logger.info("Base chain TVL: %d history points", len(history))
        return history


# ---------------------------------------------------------------------------
# On-chain data collector (Base RPC)
# ---------------------------------------------------------------------------


class OnChainCollector:
    """Reads on-chain data from Base public RPC using web3.py."""

    def __init__(self, rpc_url: str = BASE_RPC_URL) -> None:
        self._rpc_url = rpc_url
        self._limiter = RateLimiter(_RPC_MIN_INTERVAL)
        self._w3 = None

    def _get_w3(self):
        if self._w3 is None:
            try:
                from web3 import Web3
                self._w3 = Web3(Web3.HTTPProvider(self._rpc_url))
            except Exception as exc:
                logger.warning("web3 init failed: %s", exc)
        return self._w3

    async def get_utilization_aave(self, reserve_address: str) -> float | None:
        """Read Aave v3 reserve utilization via RPC."""
        w3 = self._get_w3()
        if w3 is None:
            return None

        # Aave v3 Pool on Base
        pool_address = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
        # getReserveData(address) selector
        selector = "0x35ea6a75"

        await self._limiter.wait()
        try:
            padded = reserve_address.lower().replace("0x", "").zfill(64)
            call_data = selector + padded
            result = w3.eth.call({
                "to": w3.to_checksum_address(pool_address),
                "data": call_data,
            })
            # Reserve data has many fields; utilization is derived from
            # totalStableDebt + totalVariableDebt / (totalDebt + availableLiquidity)
            # For simplicity, we parse the currentLiquidityRate (index 3 in tuple)
            # and approximate utilization
            if len(result) >= 256:
                # liquidityRate is at offset 96-128 (word 3), scaled by 1e27 (RAY)
                liquidity_rate = int.from_bytes(result[96:128], "big") / 1e27
                # rough utilization estimate from rate
                utilization = min(liquidity_rate * 10, 1.0)
                return utilization
        except Exception as exc:
            logger.debug("Aave utilization read failed for %s: %s", reserve_address, exc)
        return None

    async def get_chainlink_price(self, aggregator_address: str) -> float | None:
        """Read latest price from Chainlink aggregator."""
        w3 = self._get_w3()
        if w3 is None:
            return None

        # latestRoundData() selector
        selector = "0xfeaf968c"

        await self._limiter.wait()
        try:
            result = w3.eth.call({
                "to": w3.to_checksum_address(aggregator_address),
                "data": selector,
            })
            if len(result) >= 160:
                # answer is at offset 32-64 (word 1), int256
                answer = int.from_bytes(result[32:64], "big", signed=True)
                # Most Chainlink feeds use 8 decimals
                return answer / 1e8
        except Exception as exc:
            logger.debug("Chainlink price read failed for %s: %s", aggregator_address, exc)
        return None


# ---------------------------------------------------------------------------
# Audit lookup
# ---------------------------------------------------------------------------


def get_audit_info(protocol: str) -> tuple[float, str]:
    """Look up audit score and info for a protocol."""
    normalized = protocol.lower().replace(" ", "-")
    info = AUDIT_REGISTRY.get(normalized)
    if info:
        return info["score"], ", ".join(info["auditors"])
    return DEFAULT_AUDIT_SCORE, "unknown"


# ---------------------------------------------------------------------------
# Drawdown computation
# ---------------------------------------------------------------------------


def compute_max_drawdown(tvl_history: list[tuple[int, float]]) -> float:
    """
    Compute maximum drawdown from TVL history.

    Returns a value between 0.0 and 1.0.
    """
    if len(tvl_history) < 2:
        return 0.0

    peak = tvl_history[0][1]
    max_dd = 0.0

    for _, tvl in tvl_history:
        if tvl > peak:
            peak = tvl
        if peak > 0:
            dd = (peak - tvl) / peak
            max_dd = max(max_dd, dd)

    return min(max_dd, 1.0)


def compute_tvl_change_7d(tvl_history: list[tuple[int, float]]) -> float:
    """Compute 7-day TVL change from history. Returns fractional change."""
    if len(tvl_history) < 2:
        return 0.0

    latest_tvl = tvl_history[-1][1]
    seven_days_ago = tvl_history[-1][0] - (7 * 86400)

    # Find closest point to 7 days ago
    closest_tvl = tvl_history[0][1]
    closest_dist = abs(tvl_history[0][0] - seven_days_ago)
    for ts, tvl in tvl_history:
        dist = abs(ts - seven_days_ago)
        if dist < closest_dist:
            closest_dist = dist
            closest_tvl = tvl

    if closest_tvl == 0:
        return 0.0

    return (latest_tvl - closest_tvl) / closest_tvl


# ---------------------------------------------------------------------------
# Main collection orchestrator
# ---------------------------------------------------------------------------


async def collect_all(
    skip_onchain: bool = False,
) -> list[CollectedVault]:
    """
    Collect vault data from all free sources.

    Args:
        skip_onchain: If True, skip RPC calls (useful when RPC is unreliable).

    Returns list of CollectedVault with all available data.
    """
    llama = DeFiLlamaCollector()
    onchain = OnChainCollector() if not skip_onchain else None

    try:
        # Step 1: Get all Base pools from target protocols
        pools = await llama.get_base_pools()
        if not pools:
            logger.warning("No pools found from DeFiLlama")
            return []

        # Step 2: Get TVL history per protocol (deduplicate API slugs)
        tvl_histories: dict[str, ProtocolTVLHistory] = {}
        seen_slugs: set[str] = set()
        for project in TARGET_PROTOCOLS:
            slug = PROTOCOL_API_SLUG.get(project, project)
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            hist = await llama.get_protocol_tvl_history(slug)
            tvl_histories[slug] = hist

        # Step 3: Build CollectedVault for each pool
        results: list[CollectedVault] = []
        for pool in pools:
            audit_score, audit_info = get_audit_info(pool.project)
            slug = PROTOCOL_API_SLUG.get(pool.project, pool.project)
            tvl_hist = tvl_histories.get(slug)
            history = tvl_hist.history if tvl_hist else []

            vault = CollectedVault(
                pool_id=pool.pool_id,
                protocol=pool.project,
                symbol=pool.symbol,
                tvl_usd=pool.tvl_usd,
                apy=pool.apy or 0.0,
                audit_score=audit_score,
                audit_info=audit_info,
                tvl_history=history,
            )
            results.append(vault)

        # Step 4: Optionally enrich with on-chain data
        if onchain and results:
            logger.info("Skipping detailed on-chain reads (public RPC limitations)")
            # On-chain reads are best-effort; public RPCs often rate-limit
            # The DeFiLlama data is sufficient for training

        logger.info("Collected %d vaults total", len(results))
        return results

    finally:
        await llama.close()


async def save_raw_data(vaults: list[CollectedVault], output_dir: Path) -> Path:
    """Save raw collected data to JSON for reproducibility."""
    import json

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "raw_vaults.json"

    data = []
    for v in vaults:
        data.append({
            "pool_id": v.pool_id,
            "protocol": v.protocol,
            "symbol": v.symbol,
            "tvl_usd": v.tvl_usd,
            "apy": v.apy,
            "audit_score": v.audit_score,
            "audit_info": v.audit_info,
            "tvl_history_len": len(v.tvl_history),
            "utilization": v.utilization,
        })

    output_path.write_text(json.dumps(data, indent=2))
    logger.info("Raw data saved to %s", output_path)
    return output_path
