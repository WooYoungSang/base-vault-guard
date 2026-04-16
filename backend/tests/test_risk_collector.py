"""Tests for risk data collection."""

from __future__ import annotations

import pytest
from vault_guard.models import VaultInfo
from vault_guard.risk_collector import _audit_score, _oracle_risk, collect_risk, collect_risks


def test_collect_risk_returns_risk_profile(morpho_vault):
    risk = collect_risk(morpho_vault)
    assert risk.vault_address == morpho_vault.address
    assert 0.0 <= risk.utilization <= 1.0
    assert 0.0 <= risk.oracle_risk_score <= 1.0
    assert 0.0 <= risk.audit_score <= 1.0
    assert 0.0 <= risk.drawdown_max <= 1.0


def test_collect_risk_utilization_matches_vault(morpho_vault):
    risk = collect_risk(morpho_vault)
    assert risk.utilization == pytest.approx(morpho_vault.utilization_rate)


def test_collect_risk_sufficient_data_high_tvl(aave_vault):
    risk = collect_risk(aave_vault)
    assert risk.sufficient_data is True


def test_collect_risk_sufficient_data_zero_tvl():
    """Static registry vaults have tvl_usd=0 — treated as potentially ratable."""
    vault = VaultInfo("0xStatic", "aave_v3", "USDC", 0.0, 3.5, 0.0)
    risk = collect_risk(vault)
    assert risk.sufficient_data is True


def test_collect_risk_sufficient_data_low_tvl(low_tvl_vault):
    risk = collect_risk(low_tvl_vault)
    assert risk.sufficient_data is False


def test_audit_score_known_protocols():
    assert _audit_score("morpho") > 0.8
    assert _audit_score("aave_v3") > 0.8
    assert _audit_score("compound_v3") > 0.7


def test_audit_score_unknown_protocol_returns_fallback():
    score = _audit_score("unknown_protocol_xyz")
    assert 0.0 <= score <= 1.0


def test_oracle_risk_known_protocols():
    assert _oracle_risk("aave_v3") < 0.20
    assert _oracle_risk("aerodrome") > 0.20  # AMM TWAP is riskier


def test_oracle_risk_unknown_protocol_returns_fallback():
    score = _oracle_risk("unknown_protocol_xyz")
    assert 0.0 <= score <= 1.0


def test_collect_risks_batch(morpho_vault, aave_vault, aerodrome_vault):
    vaults = [morpho_vault, aave_vault, aerodrome_vault]
    risks = collect_risks(vaults)
    assert len(risks) == 3
    addresses = [r.vault_address for r in risks]
    assert morpho_vault.address in addresses
    assert aave_vault.address in addresses
    assert aerodrome_vault.address in addresses


def test_aerodrome_higher_drawdown_than_aave(aave_vault, aerodrome_vault):
    aave_risk = collect_risk(aave_vault)
    aero_risk = collect_risk(aerodrome_vault)
    assert aero_risk.drawdown_max > aave_risk.drawdown_max
