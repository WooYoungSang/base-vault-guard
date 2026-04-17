"""ML Scorer — XGBoost-based grade prediction with confidence."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import numpy as np
import xgboost as xgb

from vault_guard.ml.data_generator import FEATURE_NAMES, GRADE_LABELS
from vault_guard.models import RiskProfile, SafetyGrade

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path(__file__).parent / "models" / "vault_guard_model.json"

_GRADE_ENUM_MAP = {
    "A": SafetyGrade.A,
    "B": SafetyGrade.B,
    "C": SafetyGrade.C,
    "D": SafetyGrade.D,
    "F": SafetyGrade.F,
}


@dataclass
class MLPrediction:
    """Result of an ML grade prediction."""

    grade: SafetyGrade
    confidence: float
    feature_importances: dict[str, float]


class MLScorer:
    """Thread-safe XGBoost scorer that loads a model once at init."""

    def __init__(self, model_path: str | Path | None = None) -> None:
        self._model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self._booster: xgb.Booster | None = None
        self._lock = Lock()
        self._loaded = False
        self._load_model()

    def _load_model(self) -> None:
        with self._lock:
            if self._loaded:
                return
            try:
                self._booster = xgb.Booster(params={"nthread": 1})
                self._booster.load_model(str(self._model_path))
                self._loaded = True
                logger.info("MLScorer loaded model from %s", self._model_path)
            except Exception as exc:
                logger.warning("MLScorer could not load model (%s)", exc)
                self._booster = None
                self._loaded = False

    @property
    def available(self) -> bool:
        return self._booster is not None

    def _build_features(self, risk: RiskProfile) -> np.ndarray:
        """Build the 7-feature vector from a RiskProfile."""
        utilization_sq = risk.utilization ** 2
        risk_composite = (
            risk.oracle_risk_score * 0.4
            + (1.0 - risk.audit_score) * 0.3
            + risk.drawdown_max * 0.3
        )
        return np.array(
            [[
                risk.utilization,
                risk.tvl_change_7d,
                risk.oracle_risk_score,
                risk.audit_score,
                risk.drawdown_max,
                utilization_sq,
                risk_composite,
            ]],
            dtype=np.float32,
        )

    def predict(self, risk: RiskProfile) -> MLPrediction | None:
        """
        Predict grade and confidence for a risk profile.

        Returns None if the model is not available.
        """
        if not self.available:
            return None

        features = self._build_features(risk)
        dmatrix = xgb.DMatrix(features, feature_names=FEATURE_NAMES)

        with self._lock:
            probs = self._booster.predict(dmatrix)[0]

        pred_idx = int(np.argmax(probs))
        confidence = float(probs[pred_idx])
        grade_str = GRADE_LABELS[pred_idx]
        grade = _GRADE_ENUM_MAP[grade_str]

        # Feature importances
        with self._lock:
            raw_importance = self._booster.get_score(importance_type="gain")
        importances = {name: raw_importance.get(name, 0.0) for name in FEATURE_NAMES}

        return MLPrediction(
            grade=grade,
            confidence=confidence,
            feature_importances=importances,
        )
