"""Vault/Market Scanner — Base chain protocols (Morpho, Aave v3, Compound v3, Aerodrome)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from vault_guard.models import VaultInfo

logger = logging.getLogger(__name__)

BASE_RPC = "https://mainnet.base.org"

# Morpho Blue subgraph on Base (public endpoint)
MORPHO_SUBGRAPH = (
    "https://api.studio.thegraph.com/query/30834/morpho-blue-base/version/latest"
)

# Hardcoded known vault addresses for Aave v3 / Compound v3 on Base
# (subgraphs may be unavailable; using static registry is acceptable for MVP)
AAVE_V3_VAULTS: list[dict[str, Any]] = [
    {
        "address": "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5",
        "asset": "USDC",
        "protocol": "aave_v3",
    },
    {
        "address": "0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB",
        "asset": "WETH",
        "protocol": "aave_v3",
    },
]

COMPOUND_V3_VAULTS: list[dict[str, Any]] = [
    {
        "address": "0xb125E6687d4313864e53df431d5425969c15Eb2",
        "asset": "USDC",
        "protocol": "compound_v3",
    },
    {
        "address": "0x46e6b214b524310239732D51387075E0e70970bf",
        "asset": "WETH",
        "protocol": "compound_v3",
    },
]

AERODROME_VAULTS: list[dict[str, Any]] = [
    {
        "address": "0x6cDcb1C4A4D1C3C6d054b27AC5B77e89eAFb971",
        "asset": "USDC/WETH",
        "protocol": "aerodrome",
    },
]

_MORPHO_QUERY = """
{
  markets(first: 20, orderBy: totalValueLockedUSD, orderDirection: desc) {
    id
    inputToken { symbol }
    totalValueLockedUSD
    rates(where: {side: BORROWER}) { rate }
    totalBorrowBalanceUSD
    totalDepositBalanceUSD
  }
}
"""


def _utilization(borrow_usd: float, deposit_usd: float) -> float:
    if deposit_usd <= 0:
        return 0.0
    return min(borrow_usd / deposit_usd, 1.0)


async def _fetch_morpho_vaults(client: httpx.AsyncClient) -> list[VaultInfo]:
    vaults: list[VaultInfo] = []
    try:
        resp = await client.post(
            MORPHO_SUBGRAPH,
            json={"query": _MORPHO_QUERY},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        markets = data.get("markets", [])
        for m in markets:
            tvl = float(m.get("totalValueLockedUSD") or 0)
            deposit = float(m.get("totalDepositBalanceUSD") or 0)
            borrow = float(m.get("totalBorrowBalanceUSD") or 0)
            rates = m.get("rates", [])
            apy = float(rates[0]["rate"]) if rates else 0.0
            asset = (m.get("inputToken") or {}).get("symbol", "UNKNOWN")
            vaults.append(
                VaultInfo(
                    address=m["id"],
                    protocol="morpho",
                    asset=asset,
                    tvl_usd=tvl,
                    apy=apy,
                    utilization_rate=_utilization(borrow, deposit),
                )
            )
    except Exception as exc:
        logger.warning("Morpho subgraph fetch failed: %s", exc)
    return vaults


def _static_vaults(registry: list[dict[str, Any]], fallback_apy: float = 3.5) -> list[VaultInfo]:
    """Return VaultInfo for static registry entries with placeholder metrics."""
    return [
        VaultInfo(
            address=v["address"],
            protocol=v["protocol"],
            asset=v["asset"],
            tvl_usd=0.0,   # would be fetched on-chain in a full impl
            apy=fallback_apy,
            utilization_rate=0.0,
        )
        for v in registry
    ]


async def scan_vaults(http_client: httpx.AsyncClient | None = None) -> list[VaultInfo]:
    """Return VaultInfo objects for all supported Base protocol vaults."""
    own_client = http_client is None
    client = http_client or httpx.AsyncClient()
    try:
        morpho_vaults = await _fetch_morpho_vaults(client)
        aave_vaults = _static_vaults(AAVE_V3_VAULTS)
        compound_vaults = _static_vaults(COMPOUND_V3_VAULTS)
        aerodrome_vaults = _static_vaults(AERODROME_VAULTS)
        return morpho_vaults + aave_vaults + compound_vaults + aerodrome_vaults
    finally:
        if own_client:
            await client.aclose()
