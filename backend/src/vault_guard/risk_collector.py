"""Risk Data Collector — builds RiskProfile for each vault."""

from __future__ import annotations

import logging

from vault_guard.models import RiskProfile, VaultInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Audit registry — hardcoded for MVP
# Keys: lower-case vault address prefix → audit score 0.0–1.0
# ---------------------------------------------------------------------------
_AUDIT_REGISTRY: dict[str, float] = {
    # Morpho Blue core contracts — multiple audits
    "morpho": 0.95,
    # Aave v3 — extensive audits
    "aave_v3": 0.95,
    # Compound v3 — audited
    "compound_v3": 0.85,
    # Aerodrome — audited but newer
    "aerodrome": 0.75,
}

# Oracle risk scores by protocol
_ORACLE_RISK: dict[str, float] = {
    "morpho": 0.15,      # Chainlink + permissionless markets (moderate)
    "aave_v3": 0.10,     # Chainlink with circuit breakers
    "compound_v3": 0.10, # Chainlink
    "aerodrome": 0.30,   # AMM TWAP — higher manipulation risk
}

# Minimum TVL to consider vault "sufficiently data-rich"
_MIN_TVL_USD = 100_000.0


def _audit_score(protocol: str) -> float:
    return _AUDIT_REGISTRY.get(protocol.lower(), 0.5)


def _oracle_risk(protocol: str) -> float:
    return _ORACLE_RISK.get(protocol.lower(), 0.5)


def _tvl_change_7d(vault: VaultInfo) -> float:
    """
    Return estimated 7-day TVL change fraction.
    For MVP we return 0.0 (no historical data available without indexer).
    A production implementation would query a historical subgraph or database.
    """
    return 0.0


def _drawdown_max(vault: VaultInfo) -> float:
    """
    Return estimated worst historical drawdown.
    MVP: use protocol-level heuristic.
    """
    heuristics = {
        "morpho": 0.05,
        "aave_v3": 0.03,
        "compound_v3": 0.04,
        "aerodrome": 0.20,  # AMM impermanent loss exposure
    }
    return heuristics.get(vault.protocol.lower(), 0.10)


def collect_risk(vault: VaultInfo) -> RiskProfile:
    """Build a RiskProfile for a single VaultInfo."""
    sufficient = vault.tvl_usd >= _MIN_TVL_USD or vault.tvl_usd == 0.0
    # tvl_usd == 0 means static registry entry — treat as potentially rated
    return RiskProfile(
        vault_address=vault.address,
        utilization=vault.utilization_rate,
        tvl_change_7d=_tvl_change_7d(vault),
        oracle_risk_score=_oracle_risk(vault.protocol),
        audit_score=_audit_score(vault.protocol),
        drawdown_max=_drawdown_max(vault),
        sufficient_data=sufficient,
    )


def collect_risks(vaults: list[VaultInfo]) -> list[RiskProfile]:
    """Build RiskProfile for every vault in the list."""
    return [collect_risk(v) for v in vaults]
