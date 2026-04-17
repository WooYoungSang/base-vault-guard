"""Shared dataclasses for Vault Guard."""

from dataclasses import dataclass, field
from enum import Enum


class SafetyGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"
    UNRATED = "Unrated"


@dataclass
class VaultInfo:
    address: str
    protocol: str  # morpho | aave_v3 | compound_v3 | aerodrome
    asset: str
    tvl_usd: float
    apy: float  # annualised percentage (e.g. 5.2 = 5.2%)
    utilization_rate: float  # 0.0–1.0


@dataclass
class RiskProfile:
    vault_address: str
    utilization: float          # 0.0–1.0
    tvl_change_7d: float        # fractional change (0.10 = +10%)
    oracle_risk_score: float    # 0.0 (safe) – 1.0 (risky)
    audit_score: float          # 0.0 (unaudited) – 1.0 (fully audited)
    drawdown_max: float         # 0.0–1.0 (worst historical drawdown)
    sufficient_data: bool = True
    extra: dict = field(default_factory=dict)


@dataclass
class ScoredVault:
    vault: VaultInfo
    risk: RiskProfile
    score: float        # 0–100
    grade: SafetyGrade
    scoring_method: str = "rule_based"   # "ml" | "rule_based"
    ml_confidence: float | None = None
