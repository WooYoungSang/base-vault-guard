"""Shared pytest fixtures for Vault Guard tests."""

from __future__ import annotations

import pytest
from vault_guard.models import RiskProfile, SafetyGrade, ScoredVault, VaultInfo


@pytest.fixture
def morpho_vault() -> VaultInfo:
    return VaultInfo(
        address="0xMorpho001",
        protocol="morpho",
        asset="USDC",
        tvl_usd=5_000_000.0,
        apy=4.5,
        utilization_rate=0.65,
    )


@pytest.fixture
def aave_vault() -> VaultInfo:
    return VaultInfo(
        address="0xAave001",
        protocol="aave_v3",
        asset="WETH",
        tvl_usd=10_000_000.0,
        apy=3.2,
        utilization_rate=0.45,
    )


@pytest.fixture
def aerodrome_vault() -> VaultInfo:
    return VaultInfo(
        address="0xAero001",
        protocol="aerodrome",
        asset="USDC/WETH",
        tvl_usd=2_000_000.0,
        apy=12.0,
        utilization_rate=0.10,
    )


@pytest.fixture
def low_tvl_vault() -> VaultInfo:
    return VaultInfo(
        address="0xSmall001",
        protocol="morpho",
        asset="WBTC",
        tvl_usd=50_000.0,   # below MIN_TVL_USD threshold
        apy=2.0,
        utilization_rate=0.80,
    )


@pytest.fixture
def safe_risk(morpho_vault: VaultInfo) -> RiskProfile:
    return RiskProfile(
        vault_address=morpho_vault.address,
        utilization=0.40,
        tvl_change_7d=0.05,
        oracle_risk_score=0.10,
        audit_score=0.95,
        drawdown_max=0.03,
        sufficient_data=True,
    )


@pytest.fixture
def risky_risk(aerodrome_vault: VaultInfo) -> RiskProfile:
    return RiskProfile(
        vault_address=aerodrome_vault.address,
        utilization=0.92,
        tvl_change_7d=-0.25,
        oracle_risk_score=0.70,
        audit_score=0.40,
        drawdown_max=0.40,
        sufficient_data=True,
    )


@pytest.fixture
def insufficient_risk(low_tvl_vault: VaultInfo) -> RiskProfile:
    return RiskProfile(
        vault_address=low_tvl_vault.address,
        utilization=0.80,
        tvl_change_7d=0.0,
        oracle_risk_score=0.50,
        audit_score=0.50,
        drawdown_max=0.10,
        sufficient_data=False,
    )


@pytest.fixture
def scored_a(morpho_vault: VaultInfo, safe_risk: RiskProfile) -> ScoredVault:
    return ScoredVault(vault=morpho_vault, risk=safe_risk, score=88.0, grade=SafetyGrade.A)


@pytest.fixture
def scored_b(aave_vault: VaultInfo) -> ScoredVault:
    risk = RiskProfile(
        vault_address=aave_vault.address,
        utilization=0.50,
        tvl_change_7d=0.0,
        oracle_risk_score=0.15,
        audit_score=0.90,
        drawdown_max=0.05,
        sufficient_data=True,
    )
    return ScoredVault(vault=aave_vault, risk=risk, score=75.0, grade=SafetyGrade.B)


@pytest.fixture
def scored_d(aerodrome_vault: VaultInfo, risky_risk: RiskProfile) -> ScoredVault:
    return ScoredVault(vault=aerodrome_vault, risk=risky_risk, score=30.0, grade=SafetyGrade.D)
