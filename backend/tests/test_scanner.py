"""Tests for vault scanner with mocked HTTP responses."""

from __future__ import annotations

import httpx
import pytest
from vault_guard.models import VaultInfo
from vault_guard.scanner import AAVE_V3_VAULTS, _fetch_morpho_vaults, _static_vaults, scan_vaults


class MockTransport(httpx.AsyncBaseTransport):
    """Minimal mock transport that returns a canned response."""

    def __init__(self, response_json: dict):
        self._response_json = response_json

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        import json
        return httpx.Response(
            200,
            content=json.dumps(self._response_json).encode(),
            headers={"content-type": "application/json"},
        )


class ErrorTransport(httpx.AsyncBaseTransport):
    """Transport that always raises a network error."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")


_MORPHO_MOCK_RESPONSE = {
    "data": {
        "markets": [
            {
                "id": "0xMorphoMarket001",
                "inputToken": {"symbol": "USDC"},
                "totalValueLockedUSD": "5000000",
                "totalDepositBalanceUSD": "5000000",
                "totalBorrowBalanceUSD": "3250000",
                "rates": [{"rate": "4.5"}],
            },
            {
                "id": "0xMorphoMarket002",
                "inputToken": {"symbol": "WETH"},
                "totalValueLockedUSD": "8000000",
                "totalDepositBalanceUSD": "8000000",
                "totalBorrowBalanceUSD": "2000000",
                "rates": [{"rate": "2.1"}],
            },
        ]
    }
}


@pytest.mark.asyncio
async def test_scan_vaults_returns_vault_info_list():
    transport = MockTransport(_MORPHO_MOCK_RESPONSE)
    async with httpx.AsyncClient(transport=transport) as client:
        vaults = await scan_vaults(client)

    assert len(vaults) > 0
    for v in vaults:
        assert isinstance(v, VaultInfo)
        assert v.address
        assert v.protocol


@pytest.mark.asyncio
async def test_scan_vaults_includes_all_protocols():
    transport = MockTransport(_MORPHO_MOCK_RESPONSE)
    async with httpx.AsyncClient(transport=transport) as client:
        vaults = await scan_vaults(client)

    protocols = {v.protocol for v in vaults}
    assert "morpho" in protocols
    assert "aave_v3" in protocols
    assert "compound_v3" in protocols
    assert "aerodrome" in protocols


@pytest.mark.asyncio
async def test_morpho_vaults_parse_tvl_and_apy():
    transport = MockTransport(_MORPHO_MOCK_RESPONSE)
    async with httpx.AsyncClient(transport=transport) as client:
        vaults = await _fetch_morpho_vaults(client)

    assert len(vaults) == 2
    usdc_vault = next(v for v in vaults if v.asset == "USDC")
    assert usdc_vault.tvl_usd == pytest.approx(5_000_000.0)
    assert usdc_vault.apy == pytest.approx(4.5)
    assert usdc_vault.utilization_rate == pytest.approx(0.65)


@pytest.mark.asyncio
async def test_scan_vaults_graceful_on_rpc_error():
    """Should return static vaults even when subgraph is unavailable."""
    transport = ErrorTransport()
    async with httpx.AsyncClient(transport=transport) as client:
        vaults = await scan_vaults(client)

    # static vaults (aave, compound, aerodrome) must still be returned
    protocols = {v.protocol for v in vaults}
    assert "aave_v3" in protocols
    assert "compound_v3" in protocols
    assert "aerodrome" in protocols


def test_static_vaults_returns_correct_count():
    vaults = _static_vaults(AAVE_V3_VAULTS)
    assert len(vaults) == len(AAVE_V3_VAULTS)
    for v in vaults:
        assert v.protocol == "aave_v3"


@pytest.mark.asyncio
async def test_morpho_vault_utilization_capped_at_one():
    """Utilization must never exceed 1.0 even if data is inconsistent."""
    bad_data = {
        "data": {
            "markets": [
                {
                    "id": "0xBad",
                    "inputToken": {"symbol": "WBTC"},
                    "totalValueLockedUSD": "1000",
                    "totalDepositBalanceUSD": "500",
                    "totalBorrowBalanceUSD": "9999",  # borrow > deposit
                    "rates": [],
                }
            ]
        }
    }
    transport = MockTransport(bad_data)
    async with httpx.AsyncClient(transport=transport) as client:
        vaults = await _fetch_morpho_vaults(client)
    assert vaults[0].utilization_rate <= 1.0
