"""Tests for data collection pipeline: collector, processor, and end-to-end."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from vault_guard.ml.data_collector import (
    CollectedVault,
    DeFiLlamaCollector,
    PoolData,
    ProtocolTVLHistory,
    RateLimiter,
    compute_max_drawdown,
    compute_tvl_change_7d,
    get_audit_info,
)
from vault_guard.ml.data_processor import (
    _assign_label,
    _estimate_oracle_risk,
    _estimate_utilization,
    process_vaults,
    save_training_data,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_POOLS_RESPONSE = {
    "data": [
        {
            "pool": "pool-aave-usdc",
            "chain": "Base",
            "project": "aave-v3",
            "symbol": "USDC",
            "tvlUsd": 5_000_000,
            "apy": 4.5,
            "apyBase": 3.0,
            "apyReward": 1.5,
            "poolMeta": None,
        },
        {
            "pool": "pool-compound-weth",
            "chain": "Base",
            "project": "compound-v3",
            "symbol": "WETH",
            "tvlUsd": 10_000_000,
            "apy": 2.8,
            "apyBase": 2.8,
            "apyReward": 0,
            "poolMeta": None,
        },
        {
            "pool": "pool-morpho-usdc",
            "chain": "Base",
            "project": "morpho-v1",
            "symbol": "USDC",
            "tvlUsd": 3_000_000,
            "apy": 5.2,
            "apyBase": 5.2,
            "apyReward": 0,
            "poolMeta": None,
        },
        {
            "pool": "pool-aero-usdc-weth",
            "chain": "Base",
            "project": "aerodrome-v1",
            "symbol": "USDC/WETH",
            "tvlUsd": 8_000_000,
            "apy": 12.0,
            "apyBase": 12.0,
            "apyReward": 0,
            "poolMeta": None,
        },
        # Non-target protocol, should be filtered out
        {
            "pool": "pool-other",
            "chain": "Base",
            "project": "uniswap-v3",
            "symbol": "USDC/ETH",
            "tvlUsd": 1_000_000,
            "apy": 8.0,
            "apyBase": 8.0,
            "apyReward": 0,
            "poolMeta": None,
        },
        # Non-Base chain, should be filtered out
        {
            "pool": "pool-eth-aave",
            "chain": "Ethereum",
            "project": "aave-v3",
            "symbol": "USDC",
            "tvlUsd": 50_000_000,
            "apy": 3.0,
            "apyBase": 3.0,
            "apyReward": 0,
            "poolMeta": None,
        },
    ]
}

MOCK_PROTOCOL_RESPONSE = {
    "chainTvls": {
        "Base": {
            "tvl": [
                {"date": 1700000000, "totalLiquidityUSD": 1_000_000},
                {"date": 1700086400, "totalLiquidityUSD": 1_200_000},
                {"date": 1700172800, "totalLiquidityUSD": 900_000},
                {"date": 1700259200, "totalLiquidityUSD": 1_100_000},
                {"date": 1700345600, "totalLiquidityUSD": 1_500_000},
                {"date": 1700432000, "totalLiquidityUSD": 1_400_000},
                {"date": 1700518400, "totalLiquidityUSD": 1_600_000},
            ],
        },
    },
}

MOCK_CHAIN_TVL_RESPONSE = [
    {"date": 1700000000, "tvl": 500_000_000},
    {"date": 1700086400, "tvl": 510_000_000},
    {"date": 1700172800, "tvl": 520_000_000},
]


def _make_vault(
    pool_id: str = "pool-1",
    protocol: str = "aave-v3",
    symbol: str = "USDC",
    tvl_usd: float = 5_000_000,
    apy: float = 4.5,
    audit_score: float = 0.95,
    tvl_history: list | None = None,
    utilization: float | None = None,
) -> CollectedVault:
    return CollectedVault(
        pool_id=pool_id,
        protocol=protocol,
        symbol=symbol,
        tvl_usd=tvl_usd,
        apy=apy,
        audit_score=audit_score,
        audit_info="OpenZeppelin",
        tvl_history=tvl_history or [],
        utilization=utilization,
    )


# ---------------------------------------------------------------------------
# DeFiLlama collector tests
# ---------------------------------------------------------------------------


class TestDeFiLlamaCollector:
    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        return client

    async def test_get_base_pools_filters_correctly(self):
        """Only Base chain + target protocol pools are returned."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_POOLS_RESPONSE
        mock_resp.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        collector = DeFiLlamaCollector(client=mock_client)
        pools = await collector.get_base_pools()

        assert len(pools) == 4
        protocols = {p.project for p in pools}
        assert protocols == {"aave-v3", "compound-v3", "morpho-v1", "aerodrome-v1"}

    async def test_get_base_pools_parses_fields(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_POOLS_RESPONSE
        mock_resp.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        collector = DeFiLlamaCollector(client=mock_client)
        pools = await collector.get_base_pools()

        aave_pool = [p for p in pools if p.project == "aave-v3"][0]
        assert aave_pool.pool_id == "pool-aave-usdc"
        assert aave_pool.tvl_usd == 5_000_000
        assert aave_pool.apy == 4.5
        assert aave_pool.chain == "Base"

    async def test_get_base_pools_empty_response(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_resp.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        collector = DeFiLlamaCollector(client=mock_client)
        pools = await collector.get_base_pools()
        assert pools == []

    async def test_get_base_pools_handles_failure(self):
        import httpx

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("timeout")

        collector = DeFiLlamaCollector(client=mock_client)
        pools = await collector.get_base_pools()
        assert pools == []

    async def test_get_protocol_tvl_history(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_PROTOCOL_RESPONSE
        mock_resp.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        collector = DeFiLlamaCollector(client=mock_client)
        hist = await collector.get_protocol_tvl_history("aave-v3")

        assert hist.protocol == "aave-v3"
        assert len(hist.history) == 7
        # Should be sorted by timestamp
        timestamps = [h[0] for h in hist.history]
        assert timestamps == sorted(timestamps)

    async def test_get_base_chain_tvl(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_CHAIN_TVL_RESPONSE
        mock_resp.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        collector = DeFiLlamaCollector(client=mock_client)
        history = await collector.get_base_chain_tvl()

        assert len(history) == 3
        assert history[0][1] == 500_000_000


# ---------------------------------------------------------------------------
# Drawdown / TVL change computation tests
# ---------------------------------------------------------------------------


class TestComputations:
    def test_max_drawdown_basic(self):
        history = [
            (1, 100.0),
            (2, 120.0),
            (3, 80.0),   # drawdown from peak 120 = 33.3%
            (4, 110.0),
        ]
        dd = compute_max_drawdown(history)
        assert abs(dd - (120 - 80) / 120) < 0.001

    def test_max_drawdown_no_drawdown(self):
        history = [(1, 100.0), (2, 110.0), (3, 120.0)]
        dd = compute_max_drawdown(history)
        assert dd == 0.0

    def test_max_drawdown_empty(self):
        assert compute_max_drawdown([]) == 0.0

    def test_max_drawdown_single_point(self):
        assert compute_max_drawdown([(1, 100.0)]) == 0.0

    def test_tvl_change_7d_positive(self):
        now = 1700000000
        history = [
            (now - 8 * 86400, 100.0),
            (now - 7 * 86400, 100.0),
            (now, 120.0),
        ]
        change = compute_tvl_change_7d(history)
        assert abs(change - 0.20) < 0.01

    def test_tvl_change_7d_negative(self):
        now = 1700000000
        history = [
            (now - 7 * 86400, 100.0),
            (now, 80.0),
        ]
        change = compute_tvl_change_7d(history)
        assert abs(change - (-0.20)) < 0.01

    def test_tvl_change_7d_empty(self):
        assert compute_tvl_change_7d([]) == 0.0


# ---------------------------------------------------------------------------
# Audit registry tests
# ---------------------------------------------------------------------------


class TestAuditRegistry:
    def test_known_protocol(self):
        score, info = get_audit_info("aave-v3")
        assert score == 0.95
        assert "OpenZeppelin" in info

    def test_unknown_protocol(self):
        score, info = get_audit_info("some-unknown-protocol")
        assert score == 0.3
        assert info == "unknown"

    def test_case_insensitive(self):
        score, _ = get_audit_info("Morpho-V1")
        assert score == 0.90


# ---------------------------------------------------------------------------
# Data processor tests
# ---------------------------------------------------------------------------


class TestDataProcessor:
    def test_estimate_utilization_with_value(self):
        vault = _make_vault(utilization=0.75)
        assert _estimate_utilization(vault) == 0.75

    def test_estimate_utilization_from_apy(self):
        vault = _make_vault(protocol="aave-v3", apy=4.5, utilization=None)
        util = _estimate_utilization(vault)
        assert 0.0 < util < 1.0

    def test_estimate_utilization_zero_apy(self):
        vault = _make_vault(apy=0, utilization=None)
        assert _estimate_utilization(vault) == 0.5

    def test_estimate_oracle_risk_stablecoin(self):
        vault = _make_vault(symbol="USDC")
        risk = _estimate_oracle_risk(vault)
        assert risk <= 0.15

    def test_estimate_oracle_risk_major_asset(self):
        vault = _make_vault(symbol="WETH")
        risk = _estimate_oracle_risk(vault)
        assert risk <= 0.20

    def test_estimate_oracle_risk_exotic(self):
        vault = _make_vault(symbol="SOME-EXOTIC-TOKEN")
        risk = _estimate_oracle_risk(vault)
        assert risk >= 0.30

    def test_estimate_oracle_risk_pair(self):
        vault = _make_vault(symbol="USDC/WETH")
        risk = _estimate_oracle_risk(vault)
        assert risk <= 0.20  # contains major assets

    def test_process_vaults_produces_features(self):
        vaults = [
            _make_vault(
                pool_id="p1", protocol="aave-v3", symbol="USDC",
                tvl_usd=5e6, apy=4.5, audit_score=0.95,
                tvl_history=[(1, 100.0), (2, 110.0)],
            ),
            _make_vault(
                pool_id="p2", protocol="aerodrome", symbol="USDC/WETH",
                tvl_usd=8e6, apy=12.0, audit_score=0.85,
                tvl_history=[(1, 200.0), (2, 180.0)],
            ),
        ]
        df = process_vaults(vaults)
        assert len(df) == 2
        assert "utilization" in df.columns
        assert "tvl_change_7d" in df.columns
        assert "oracle_risk_score" in df.columns
        assert "audit_score" in df.columns
        assert "drawdown_max" in df.columns
        assert "utilization_squared" in df.columns
        assert "risk_composite" in df.columns
        assert "label" in df.columns

    def test_process_vaults_empty(self):
        df = process_vaults([])
        assert df.empty

    def test_process_vaults_features_in_range(self):
        vaults = [
            _make_vault(tvl_history=[(i, 100 + i * 10) for i in range(10)]),
        ]
        df = process_vaults(vaults)
        assert (df["utilization"] >= 0).all() and (df["utilization"] <= 1).all()
        assert (df["oracle_risk_score"] >= 0).all() and (df["oracle_risk_score"] <= 1).all()
        assert (df["audit_score"] >= 0).all() and (df["audit_score"] <= 1).all()
        assert (df["drawdown_max"] >= 0).all() and (df["drawdown_max"] <= 1).all()

    def test_assign_label_safe_vault(self):
        row = pd.Series({
            "utilization": 0.3,
            "tvl_change_7d": 0.05,
            "oracle_risk_score": 0.05,
            "audit_score": 0.95,
            "drawdown_max": 0.02,
        })
        label = _assign_label(row)
        assert label in (0, 1)  # A or B

    def test_assign_label_risky_vault(self):
        row = pd.Series({
            "utilization": 0.95,
            "tvl_change_7d": -0.30,
            "oracle_risk_score": 0.80,
            "audit_score": 0.10,
            "drawdown_max": 0.60,
        })
        label = _assign_label(row)
        assert label in (3, 4)  # D or F

    def test_save_training_data(self, tmp_path):
        vaults = [
            _make_vault(
                pool_id=f"p{i}", tvl_history=[(j, 100 + j) for j in range(5)],
            )
            for i in range(5)
        ]
        df = process_vaults(vaults)
        csv_path = tmp_path / "test_training.csv"
        save_training_data(df, csv_path)

        assert csv_path.exists()
        loaded = pd.read_csv(csv_path)
        assert len(loaded) == 5
        assert "label" in loaded.columns
        assert "utilization" in loaded.columns


# ---------------------------------------------------------------------------
# End-to-end pipeline test (all mocked)
# ---------------------------------------------------------------------------


class TestCollectPipeline:
    async def test_collect_all_integration(self):
        """End-to-end test with mocked HTTP responses."""
        from vault_guard.ml.data_collector import collect_all

        mock_pools_resp = MagicMock()
        mock_pools_resp.json.return_value = MOCK_POOLS_RESPONSE
        mock_pools_resp.raise_for_status.return_value = None

        mock_protocol_resp = MagicMock()
        mock_protocol_resp.json.return_value = MOCK_PROTOCOL_RESPONSE
        mock_protocol_resp.raise_for_status.return_value = None

        async def mock_get(url):
            if "pools" in url:
                return mock_pools_resp
            return mock_protocol_resp

        mock_client = AsyncMock()
        mock_client.get.side_effect = mock_get
        mock_client.aclose = AsyncMock()

        # Patch DeFiLlamaCollector to inject our mock client
        with patch(
            "vault_guard.ml.data_collector.DeFiLlamaCollector.__init__",
            lambda self, client=None: (
                setattr(self, "_client", mock_client),
                setattr(self, "_owns_client", True),
                setattr(self, "_limiter", RateLimiter(0)),
            ) and None,
        ):
            vaults = await collect_all(skip_onchain=True)

        assert len(vaults) == 4
        protocols = {v.protocol for v in vaults}
        assert "aave-v3" in protocols

        # Process into features
        df = process_vaults(vaults)
        assert len(df) == 4
        assert "label" in df.columns
        assert all(0 <= label <= 4 for label in df["label"])
