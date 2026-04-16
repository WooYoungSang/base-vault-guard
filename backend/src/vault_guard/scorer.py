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
# XGBoost scorer (optional — falls back to rule-based if unavailable)
# ---------------------------------------------------------------------------

_xgb_model = None   # lazy-loaded


def _features(risk: RiskProfile) -> list[float]:
    return [
        risk.utilization,
        risk.tvl_change_7d,
        risk.oracle_risk_score,
        risk.audit_score,
        risk.drawdown_max,
    ]


def _try_load_xgb_model(model_path: str = "models/vault_guard_xgb.json") -> object | None:
    try:
        import xgboost as xgb  # noqa: PLC0415

        booster = xgb.Booster()
        booster.load_model(model_path)
        logger.info("XGBoost model loaded from %s", model_path)
        return booster
    except Exception as exc:
        logger.info("XGBoost model not available (%s); using rule-based scorer", exc)
        return None


def _xgb_score(risk: RiskProfile, model: object) -> float:
    """Score using loaded XGBoost model. Returns 0–100."""
    try:
        import xgboost as xgb  # noqa: PLC0415

        feats = np.array([_features(risk)], dtype=np.float32)
        dmatrix = xgb.DMatrix(feats, feature_names=list(_WEIGHTS.keys()))
        prob = float(model.predict(dmatrix)[0])  # P(safe)
        return round(prob * 100.0, 2)
    except Exception as exc:
        logger.warning("XGBoost inference failed (%s); falling back to rule-based", exc)
        return rule_based_score(risk)


def score_vault(
    vault: VaultInfo,
    risk: RiskProfile,
    *,
    model_path: str = "models/vault_guard_xgb.json",
    use_ml: bool = True,
) -> ScoredVault:
    """
    Score a vault and return a ScoredVault with numeric score and letter grade.

    If the vault has insufficient data, grade is set to UNRATED.
    """
    if not risk.sufficient_data:
        return ScoredVault(vault=vault, risk=risk, score=0.0, grade=SafetyGrade.UNRATED)

    global _xgb_model  # noqa: PLW0603
    if use_ml and _xgb_model is None:
        _xgb_model = _try_load_xgb_model(model_path)

    if use_ml and _xgb_model is not None:
        score = _xgb_score(risk, _xgb_model)
    else:
        score = rule_based_score(risk)

    grade = _score_to_grade(score)
    return ScoredVault(vault=vault, risk=risk, score=score, grade=grade)


def score_vaults(
    vaults: list[VaultInfo],
    risks: list[RiskProfile],
    **kwargs,
) -> list[ScoredVault]:
    """Batch-score vaults; risks must align positionally with vaults."""
    return [score_vault(v, r, **kwargs) for v, r in zip(vaults, risks)]
