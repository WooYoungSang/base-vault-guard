"""Pydantic v2 response schemas for Vault Guard API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

DISCLAIMER = (
    "Safety scores are informational only, not financial advice. "
    "DeFi investments carry significant risk including total loss of funds."
)


class VaultSchema(BaseModel):
    address: str
    protocol: str
    asset: str
    tvl_usd: float
    apy: float
    utilization_rate: float


class RiskProfileSchema(BaseModel):
    utilization: float
    tvl_change_7d: float
    oracle_risk_score: float
    audit_score: float
    drawdown_max: float
    sufficient_data: bool


class ScoredVaultSchema(BaseModel):
    vault: VaultSchema
    risk: RiskProfileSchema
    score: float
    grade: str
    scoring_method: str = "rule_based"
    ml_confidence: float | None = None
    disclaimer: str = Field(default=DISCLAIMER)


class VaultListResponse(BaseModel):
    items: list[ScoredVaultSchema]
    total: int
    page: int
    page_size: int
    disclaimer: str = Field(default=DISCLAIMER)


class GradeHistoryRecord(BaseModel):
    grade: str
    score: float
    recorded_at: datetime


class VaultHistoryResponse(BaseModel):
    vault_address: str
    history: list[GradeHistoryRecord]


class SafeYieldResponse(BaseModel):
    items: list[ScoredVaultSchema]
    min_grade: str
    total: int
    disclaimer: str = Field(default=DISCLAIMER)


class HealthResponse(BaseModel):
    status: str
    vault_count: int
    last_refresh: datetime | None
