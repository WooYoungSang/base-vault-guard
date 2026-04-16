"""Tests for safety scoring logic (rule-based + ML fallback)."""

from __future__ import annotations

import pytest
from vault_guard.models import RiskProfile, SafetyGrade
from vault_guard.scorer import _score_to_grade, rule_based_score, score_vault


def test_grade_thresholds():
    assert _score_to_grade(90) == SafetyGrade.A
    assert _score_to_grade(85) == SafetyGrade.A
    assert _score_to_grade(84) == SafetyGrade.B
    assert _score_to_grade(70) == SafetyGrade.B
    assert _score_to_grade(69) == SafetyGrade.C
    assert _score_to_grade(55) == SafetyGrade.C
    assert _score_to_grade(54) == SafetyGrade.D
    assert _score_to_grade(35) == SafetyGrade.D
    assert _score_to_grade(34) == SafetyGrade.F
    assert _score_to_grade(0) == SafetyGrade.F


def test_rule_based_score_safe_vault(safe_risk):
    score = rule_based_score(safe_risk)
    assert 70 <= score <= 100, f"Expected high score for safe vault, got {score}"


def test_rule_based_score_risky_vault(risky_risk):
    score = rule_based_score(risky_risk)
    assert 0 <= score <= 55, f"Expected low score for risky vault, got {score}"


def test_rule_based_score_bounds():
    """Score must always be in [0, 100]."""
    edge_cases = [
        RiskProfile("0x0", 0.0, 1.0, 0.0, 1.0, 0.0, sufficient_data=True),
        RiskProfile("0x1", 1.0, -1.0, 1.0, 0.0, 1.0, sufficient_data=True),
        RiskProfile("0x2", 0.5, 0.0, 0.5, 0.5, 0.5, sufficient_data=True),
    ]
    for risk in edge_cases:
        score = rule_based_score(risk)
        assert 0 <= score <= 100


def test_rule_based_score_high_utilization_lowers_score():
    low_util = RiskProfile("0xA", 0.10, 0.0, 0.10, 0.90, 0.05, sufficient_data=True)
    high_util = RiskProfile("0xB", 0.95, 0.0, 0.10, 0.90, 0.05, sufficient_data=True)
    assert rule_based_score(low_util) > rule_based_score(high_util)


def test_rule_based_score_tvl_drop_lowers_score():
    stable = RiskProfile("0xA", 0.50, 0.0, 0.20, 0.80, 0.05, sufficient_data=True)
    dropping = RiskProfile("0xB", 0.50, -0.30, 0.20, 0.80, 0.05, sufficient_data=True)
    assert rule_based_score(stable) > rule_based_score(dropping)


def test_score_vault_unrated_when_insufficient_data(low_tvl_vault, insufficient_risk):
    result = score_vault(low_tvl_vault, insufficient_risk, use_ml=False)
    assert result.grade == SafetyGrade.UNRATED
    assert result.score == 0.0


def test_score_vault_returns_scored_vault(morpho_vault, safe_risk):
    result = score_vault(morpho_vault, safe_risk, use_ml=False)
    assert result.vault is morpho_vault
    assert result.risk is safe_risk
    assert isinstance(result.grade, SafetyGrade)
    assert 0 <= result.score <= 100


def test_score_vault_rule_based_no_ml(morpho_vault, safe_risk):
    result = score_vault(morpho_vault, safe_risk, use_ml=False)
    expected_score = rule_based_score(safe_risk)
    assert result.score == pytest.approx(expected_score)


def test_score_vault_safe_gets_good_grade(morpho_vault, safe_risk):
    result = score_vault(morpho_vault, safe_risk, use_ml=False)
    assert result.grade in (SafetyGrade.A, SafetyGrade.B)


def test_score_vault_risky_gets_bad_grade(aerodrome_vault, risky_risk):
    result = score_vault(aerodrome_vault, risky_risk, use_ml=False)
    assert result.grade in (SafetyGrade.D, SafetyGrade.F)


def test_score_vault_ml_falls_back_to_rule_based(morpho_vault, safe_risk):
    """When model file doesn't exist, ML should silently fallback to rule-based."""
    result = score_vault(morpho_vault, safe_risk, model_path="/nonexistent/model.json", use_ml=True)
    assert result.grade != SafetyGrade.UNRATED
    assert 0 <= result.score <= 100
