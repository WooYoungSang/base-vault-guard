"""Tests for ML scoring: data generation, training, prediction, and fallback."""

from __future__ import annotations

import numpy as np
import pytest
from vault_guard.ml.data_generator import GRADE_LABELS, generate_training_data
from vault_guard.ml.ml_scorer import MLScorer
from vault_guard.ml.trainer import train_model
from vault_guard.models import RiskProfile, SafetyGrade
from vault_guard.scorer import rule_based_score, score_vault

# ---------------------------------------------------------------------------
# Data generation tests
# ---------------------------------------------------------------------------


class TestDataGenerator:
    def test_generates_correct_sample_count(self):
        X, y = generate_training_data(n_samples=500, seed=1)
        # n_samples + 4 edge cases
        assert len(X) >= 500
        assert len(y) == len(X)

    def test_all_grades_represented(self):
        _, y = generate_training_data(n_samples=1000, seed=2)
        unique = set(y.tolist())
        assert unique == {0, 1, 2, 3, 4}, f"Missing grades: {unique}"

    def test_grade_distribution_reasonable(self):
        _, y = generate_training_data(n_samples=2000, seed=3)
        counts = {label: 0 for label in GRADE_LABELS}
        for val in y:
            counts[GRADE_LABELS[val]] += 1
        # Each grade should have at least 5% of samples
        for label, count in counts.items():
            assert count >= 100, f"Grade {label} underrepresented: {count}"

    def test_features_in_valid_ranges(self):
        X, _ = generate_training_data(n_samples=500, seed=4)
        assert (X["utilization"] >= 0).all() and (X["utilization"] <= 1).all()
        assert (X["oracle_risk_score"] >= 0).all() and (X["oracle_risk_score"] <= 1).all()
        assert (X["audit_score"] >= 0).all() and (X["audit_score"] <= 1).all()
        assert (X["drawdown_max"] >= 0).all() and (X["drawdown_max"] <= 1).all()

    def test_derived_features_present(self):
        X, _ = generate_training_data(n_samples=100, seed=5)
        assert "utilization_squared" in X.columns
        assert "risk_composite" in X.columns

    def test_utilization_squared_correct(self):
        X, _ = generate_training_data(n_samples=100, seed=6)
        expected = X["utilization"] ** 2
        np.testing.assert_allclose(X["utilization_squared"], expected, rtol=1e-6)


# ---------------------------------------------------------------------------
# Model training tests
# ---------------------------------------------------------------------------


class TestTrainer:
    @pytest.fixture(scope="class")
    def trained_model(self, tmp_path_factory):
        save_dir = tmp_path_factory.mktemp("model")
        metrics = train_model(n_samples=2500, seed=42, save_dir=save_dir)
        metrics["save_dir"] = save_dir
        return metrics

    def test_model_file_created(self, trained_model):
        save_dir = trained_model["save_dir"]
        assert (save_dir / "vault_guard_model.json").exists()
        assert (save_dir / "feature_metadata.json").exists()

    def test_accuracy_above_threshold(self, trained_model):
        assert trained_model["accuracy"] >= 0.80, (
            f"Accuracy {trained_model['accuracy']:.4f} below 0.80"
        )

    def test_macro_auc_above_threshold(self, trained_model):
        assert trained_model["macro_auc"] >= 0.80, (
            f"Macro AUC {trained_model['macro_auc']:.4f} below 0.80"
        )

    def test_per_class_precision_recall(self, trained_model):
        report = trained_model["per_class_report"]
        for grade in GRADE_LABELS:
            info = report[grade]
            # Each class should have reasonable precision and recall
            assert info["precision"] >= 0.50, (
                f"Grade {grade} precision {info['precision']:.3f} below 0.50"
            )
            assert info["recall"] >= 0.50, (
                f"Grade {grade} recall {info['recall']:.3f} below 0.50"
            )


# ---------------------------------------------------------------------------
# MLScorer prediction tests
# ---------------------------------------------------------------------------


class TestMLScorer:
    @pytest.fixture(scope="class")
    def model_dir(self, tmp_path_factory):
        save_dir = tmp_path_factory.mktemp("scorer_model")
        train_model(n_samples=2500, seed=42, save_dir=save_dir)
        return save_dir

    @pytest.fixture
    def scorer(self, model_dir):
        return MLScorer(model_path=model_dir / "vault_guard_model.json")

    def test_scorer_available(self, scorer):
        assert scorer.available is True

    def test_predict_safe_vault(self, scorer):
        risk = RiskProfile(
            "0xSafe", 0.30, 0.05, 0.08, 0.95, 0.02, sufficient_data=True,
        )
        pred = scorer.predict(risk)
        assert pred is not None
        assert pred.grade in (SafetyGrade.A, SafetyGrade.B)
        assert 0.0 <= pred.confidence <= 1.0

    def test_predict_risky_vault(self, scorer):
        risk = RiskProfile(
            "0xRisky", 0.95, -0.30, 0.80, 0.10, 0.60, sufficient_data=True,
        )
        pred = scorer.predict(risk)
        assert pred is not None
        assert pred.grade in (SafetyGrade.D, SafetyGrade.F)
        assert 0.0 <= pred.confidence <= 1.0

    def test_predict_returns_feature_importances(self, scorer):
        risk = RiskProfile(
            "0xTest", 0.50, 0.0, 0.30, 0.70, 0.10, sufficient_data=True,
        )
        pred = scorer.predict(risk)
        assert pred is not None
        assert isinstance(pred.feature_importances, dict)
        assert len(pred.feature_importances) > 0

    def test_scorer_not_available_with_bad_path(self):
        scorer = MLScorer(model_path="/nonexistent/model.json")
        assert scorer.available is False
        risk = RiskProfile(
            "0xTest", 0.50, 0.0, 0.30, 0.70, 0.10, sufficient_data=True,
        )
        assert scorer.predict(risk) is None


# ---------------------------------------------------------------------------
# Scorer integration tests (fallback behavior)
# ---------------------------------------------------------------------------


class TestScorerIntegration:
    def test_fallback_when_model_missing(self, morpho_vault, safe_risk):
        """When model path doesn't exist, falls back to rule-based."""
        result = score_vault(
            morpho_vault, safe_risk,
            model_path="/nonexistent/model.json", use_ml=True,
        )
        assert result.scoring_method == "rule_based"
        assert result.ml_confidence is None
        assert result.grade != SafetyGrade.UNRATED
        assert 0 <= result.score <= 100

    def test_rule_based_explicit(self, morpho_vault, safe_risk):
        """use_ml=False always uses rule-based."""
        result = score_vault(morpho_vault, safe_risk, use_ml=False)
        assert result.scoring_method == "rule_based"
        assert result.ml_confidence is None
        expected = rule_based_score(safe_risk)
        assert result.score == pytest.approx(expected)

    def test_unrated_still_works(self, low_tvl_vault, insufficient_risk):
        """Insufficient data should still return UNRATED."""
        result = score_vault(low_tvl_vault, insufficient_risk, use_ml=True)
        assert result.grade == SafetyGrade.UNRATED
        assert result.score == 0.0
        assert result.scoring_method == "rule_based"

    def test_scoring_method_field_present(self, morpho_vault, safe_risk):
        """ScoredVault always has scoring_method field."""
        result = score_vault(morpho_vault, safe_risk, use_ml=False)
        assert hasattr(result, "scoring_method")
        assert result.scoring_method in ("ml", "rule_based")

    def test_ml_confidence_field_present(self, morpho_vault, safe_risk):
        """ScoredVault always has ml_confidence field."""
        result = score_vault(morpho_vault, safe_risk, use_ml=False)
        assert hasattr(result, "ml_confidence")
