"""Tests for FastAPI endpoints using TestClient."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from vault_guard.models import RiskProfile, SafetyGrade, ScoredVault, VaultInfo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MOCK_VAULTS = [
    VaultInfo("0xAAA", "morpho", "USDC", 5_000_000.0, 4.5, 0.60),
    VaultInfo("0xBBB", "aave_v3", "WETH", 10_000_000.0, 3.2, 0.45),
    VaultInfo("0xCCC", "aerodrome", "USDC/WETH", 2_000_000.0, 12.0, 0.10),
]

_MOCK_RISKS = [
    RiskProfile("0xAAA", 0.60, 0.0, 0.15, 0.95, 0.05, True),
    RiskProfile("0xBBB", 0.45, 0.0, 0.10, 0.95, 0.03, True),
    RiskProfile("0xCCC", 0.10, 0.0, 0.30, 0.75, 0.20, True),
]


def _make_scored(vault, risk, score, grade_str) -> ScoredVault:
    return ScoredVault(vault=vault, risk=risk, score=score, grade=SafetyGrade(grade_str))


_MOCK_SCORED = [
    _make_scored(_MOCK_VAULTS[0], _MOCK_RISKS[0], 85.0, "A"),
    _make_scored(_MOCK_VAULTS[1], _MOCK_RISKS[1], 78.0, "B"),
    _make_scored(_MOCK_VAULTS[2], _MOCK_RISKS[2], 60.0, "C"),
]


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_history.db"


@pytest.fixture
def client(tmp_db: Path):
    """Return a TestClient with the pipeline mocked to return fixed scored vaults."""
    import vault_guard.api as api_module

    api_module._DB_PATH = tmp_db
    api_module._cache.clear()
    api_module._last_refresh = None

    with patch(
        "vault_guard.api._run_pipeline",
        new_callable=AsyncMock,
        return_value=_MOCK_SCORED,
    ):
        # Prime cache
        import asyncio
        asyncio.get_event_loop().run_until_complete(api_module._get_scored_vaults())

        with TestClient(api_module.app, raise_server_exceptions=True) as c:
            yield c


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["vault_count"] == 3


# ---------------------------------------------------------------------------
# GET /vaults
# ---------------------------------------------------------------------------


def test_list_vaults_returns_all(client):
    resp = client.get("/vaults")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_list_vaults_includes_disclaimer(client):
    resp = client.get("/vaults")
    data = resp.json()
    assert "informational only" in data["disclaimer"].lower()


def test_list_vaults_filter_by_protocol(client):
    resp = client.get("/vaults?protocol=morpho")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["vault"]["protocol"] == "morpho"


def test_list_vaults_filter_by_grade(client):
    resp = client.get("/vaults?grade=A")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["grade"] == "A"


def test_list_vaults_invalid_grade_returns_400(client):
    resp = client.get("/vaults?grade=Z")
    assert resp.status_code == 400


def test_list_vaults_pagination(client):
    resp = client.get("/vaults?page=1&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["page_size"] == 2


def test_list_vaults_page_2(client):
    resp = client.get("/vaults?page=2&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1


def test_list_vaults_items_have_required_fields(client):
    resp = client.get("/vaults")
    item = resp.json()["items"][0]
    assert "vault" in item
    assert "risk" in item
    assert "score" in item
    assert "grade" in item
    vault = item["vault"]
    for field in ("address", "protocol", "asset", "tvl_usd", "apy", "utilization_rate"):
        assert field in vault


# ---------------------------------------------------------------------------
# GET /vaults/{address}
# ---------------------------------------------------------------------------


def test_vault_detail_found(client):
    resp = client.get("/vaults/0xAAA")
    assert resp.status_code == 200
    data = resp.json()
    assert data["vault"]["address"] == "0xAAA"
    assert data["grade"] == "A"
    assert data["score"] == pytest.approx(85.0)


def test_vault_detail_case_insensitive(client):
    resp = client.get("/vaults/0xaaa")
    assert resp.status_code == 200


def test_vault_detail_not_found(client):
    resp = client.get("/vaults/0xDEAD")
    assert resp.status_code == 404


def test_vault_detail_has_risk_breakdown(client):
    resp = client.get("/vaults/0xBBB")
    data = resp.json()
    risk = data["risk"]
    assert "utilization" in risk
    assert "oracle_risk_score" in risk
    assert "audit_score" in risk
    assert "drawdown_max" in risk


def test_vault_detail_has_disclaimer(client):
    resp = client.get("/vaults/0xAAA")
    data = resp.json()
    assert "informational only" in data["disclaimer"].lower()


# ---------------------------------------------------------------------------
# GET /vaults/safe-yield
# ---------------------------------------------------------------------------


def test_safe_yield_default_min_grade_b(client):
    resp = client.get("/vaults/safe-yield")
    assert resp.status_code == 200
    data = resp.json()
    assert data["min_grade"] == "B"
    for item in data["items"]:
        assert item["grade"] in ("A", "B")


def test_safe_yield_sorted_by_apy(client):
    resp = client.get("/vaults/safe-yield?min_grade=A")
    data = resp.json()
    apys = [item["vault"]["apy"] for item in data["items"]]
    assert apys == sorted(apys, reverse=True)


def test_safe_yield_min_grade_c_includes_c(client):
    resp = client.get("/vaults/safe-yield?min_grade=C")
    data = resp.json()
    grades = {item["grade"] for item in data["items"]}
    assert "C" in grades


def test_safe_yield_invalid_grade_returns_400(client):
    resp = client.get("/vaults/safe-yield?min_grade=X")
    assert resp.status_code == 400


def test_safe_yield_has_disclaimer(client):
    resp = client.get("/vaults/safe-yield")
    data = resp.json()
    assert "informational only" in data["disclaimer"].lower()


# ---------------------------------------------------------------------------
# GET /vaults/{address}/history
# ---------------------------------------------------------------------------


def test_vault_history_empty_for_new_vault(client, tmp_db):
    from vault_guard.history import init_db
    init_db(tmp_db)
    resp = client.get("/vaults/0xNEW/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["vault_address"] == "0xNEW"
    assert data["history"] == []


def test_vault_history_returns_records(client, tmp_db):
    from vault_guard.history import init_db, record_grade
    init_db(tmp_db)
    record_grade("0xAAA", SafetyGrade.A, 88.0, tmp_db)
    record_grade("0xAAA", SafetyGrade.B, 72.0, tmp_db)

    resp = client.get("/vaults/0xAAA/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["history"]) == 2
    assert data["history"][0]["grade"] in ("A", "B")


def test_vault_history_record_has_fields(client, tmp_db):
    from vault_guard.history import init_db, record_grade
    init_db(tmp_db)
    record_grade("0xBBB", SafetyGrade.B, 75.0, tmp_db)

    resp = client.get("/vaults/0xBBB/history")
    record = resp.json()["history"][0]
    assert "grade" in record
    assert "score" in record
    assert "recorded_at" in record
