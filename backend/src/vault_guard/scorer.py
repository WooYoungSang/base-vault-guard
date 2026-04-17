"""ML Safety Scorer — XGBoost classifier with rule-based fallback."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from vault_guard.models import RiskProfile, SafetyGrade, ScoredVault, VaultInfo

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Grade thresholds (score 0–100)
# ---------------------------------------------------------------------------
_GRADE_THRESHOLDS = [
    (85, SafetyGrade.A),
    (70, SafetyGrade.B),
    (55, SafetyGrade.C),
    (35, SafetyGrade.D),
    (0,  SafetyGrade.F),
]

# ---------------------------------------------------------------------------
# Rule-based weights
# Higher weight = more impact on safety score
# ---------------------------------------------------------------------------
_WEIGHTS = {
    "utilization":       0.20,   # high utilization → liquidity risk
    "tvl_change_7d":     0.15,   # steep TVL drop → red flag
    "oracle_risk_score": 0.25,   # oracle manipulation is critical
    "audit_score":       0.25,   # audit coverage is critical
    "drawdown_max":      0.15,   # historical drawdown
}

# Minimum ML confidence to trust the model prediction
_ML_CONFIDENCE_THRESHOLD = 0.6


def _score_to_grade(score: float) -> SafetyGrade:
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return SafetyGrade.F


def rule_based_score(risk: RiskProfile) -> float:
    """
    Compute a safety score in [0, 100] using a weighted rule-based formula.

    Higher score = safer vault.

    Each feature is normalised to a 0–1 "safety contribution":
    - utilization:       1 - utilization  (low utilization is safer)
    - tvl_change_7d:     sigmoid-like: penalise drops, reward stability
    - oracle_risk_score: 1 - oracle_risk  (lower oracle risk is safer)
    - audit_score:       audit_score      (higher is safer)
    - drawdown_max:      1 - drawdown_max (lower drawdown is safer)
    """
    util_safe = 1.0 - min(risk.utilization, 1.0)

    # tvl_change_7d: -0.3 or below → 0.0 safety; 0 → 0.5; +0.3 → 1.0
    tvl_safe = min(max((risk.tvl_change_7d + 0.3) / 0.6, 0.0), 1.0)

    oracle_safe = 1.0 - min(risk.oracle_risk_score, 1.0)
    audit_safe = min(risk.audit_score, 1.0)
    drawdown_safe = 1.0 - min(risk.drawdown_max, 1.0)

    score = (
        _WEIGHTS["utilization"] * util_safe
        + _WEIGHTS["tvl_change_7d"] * tvl_safe
        + _WEIGHTS["oracle_risk_score"] * oracle_safe
        + _WEIGHTS["audit_score"] * audit_safe
        + _WEIGHTS["drawdown_max"] * drawdown_safe
    ) * 100.0

    return round(float(np.clip(score, 0.0, 100.0)), 2)


# ---------------------------------------------------------------------------
# MLScorer singleton (lazy-loaded, thread-safe)
# ---------------------------------------------------------------------------

_ml_scorer = None  # lazy-loaded


def _get_ml_scorer(model_path: str | None = None):
    """Lazily load the MLScorer singleton."""
    global _ml_scorer  # noqa: PLW0603
    if _ml_scorer is not None:
        return _ml_scorer
    try:
        from vault_guard.ml.ml_scorer import MLScorer  # noqa: PLC0415

        _ml_scorer = MLScorer(model_path=model_path)
        if not _ml_scorer.available:
            _ml_scorer = None
    except Exception as exc:
        logger.info("MLScorer not available (%s); using rule-based scorer", exc)
        _ml_scorer = None
    return _ml_scorer


def score_vault(
    vault: VaultInfo,
    risk: RiskProfile,
    *,
    model_path: str | None = None,
    use_ml: bool = True,
) -> ScoredVault:
    """
    Score a vault and return a ScoredVault with numeric score and letter grade.

    If the vault has insufficient data, grade is set to UNRATED.
    ML prediction is tried first; falls back to rule-based if confidence < 0.6
    or model is unavailable.
    """
    if not risk.sufficient_data:
        return ScoredVault(
            vault=vault, risk=risk, score=0.0, grade=SafetyGrade.UNRATED,
            scoring_method="rule_based", ml_confidence=None,
        )

    # Try ML scoring
    if use_ml:
        scorer = _get_ml_scorer(model_path)
        if scorer is not None:
            prediction = scorer.predict(risk)
            if prediction is not None and prediction.confidence >= _ML_CONFIDENCE_THRESHOLD:
                # Use ML-derived grade; compute rule-based score for the numeric value
                rb_score = rule_based_score(risk)
                return ScoredVault(
                    vault=vault,
                    risk=risk,
                    score=rb_score,
                    grade=prediction.grade,
                    scoring_method="ml",
                    ml_confidence=round(prediction.confidence, 4),
                )

    # Fallback to rule-based
    score = rule_based_score(risk)
    grade = _score_to_grade(score)
    return ScoredVault(
        vault=vault, risk=risk, score=score, grade=grade,
        scoring_method="rule_based", ml_confidence=None,
    )


def score_vaults(
    vaults: list[VaultInfo],
    risks: list[RiskProfile],
    **kwargs,
) -> list[ScoredVault]:
    """Batch-score vaults; risks must align positionally with vaults."""
    return [score_vault(v, r, **kwargs) for v, r in zip(vaults, risks)]
