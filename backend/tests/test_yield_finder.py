"""Tests for safe yield finder — filtering and sorting."""

from __future__ import annotations

from vault_guard.models import SafetyGrade, ScoredVault
from vault_guard.yield_finder import _grade_rank, find_safe_yields


def test_grade_rank_ordering():
    assert _grade_rank(SafetyGrade.A) < _grade_rank(SafetyGrade.B)
    assert _grade_rank(SafetyGrade.B) < _grade_rank(SafetyGrade.C)
    assert _grade_rank(SafetyGrade.C) < _grade_rank(SafetyGrade.D)
    assert _grade_rank(SafetyGrade.D) < _grade_rank(SafetyGrade.F)
    assert _grade_rank(SafetyGrade.UNRATED) > _grade_rank(SafetyGrade.F)


def test_find_safe_yields_excludes_below_min_grade(scored_a, scored_b, scored_d):
    results = find_safe_yields([scored_a, scored_b, scored_d], min_grade=SafetyGrade.B)
    grades = {sv.grade for sv in results}
    assert SafetyGrade.D not in grades
    assert SafetyGrade.A in grades or SafetyGrade.B in grades


def test_find_safe_yields_excludes_unrated(morpho_vault, safe_risk, scored_a):
    unrated = ScoredVault(
        vault=morpho_vault,
        risk=safe_risk,
        score=0.0,
        grade=SafetyGrade.UNRATED,
    )
    results = find_safe_yields([scored_a, unrated], min_grade=SafetyGrade.C)
    assert all(sv.grade != SafetyGrade.UNRATED for sv in results)


def test_find_safe_yields_sorted_by_apy_descending(scored_a, scored_b):
    # scored_a vault has apy=4.5, scored_b vault has apy=3.2
    results = find_safe_yields([scored_b, scored_a], min_grade=SafetyGrade.B)
    assert len(results) >= 2
    apys = [sv.vault.apy for sv in results]
    assert apys == sorted(apys, reverse=True)


def test_find_safe_yields_empty_list():
    results = find_safe_yields([], min_grade=SafetyGrade.A)
    assert results == []


def test_find_safe_yields_all_fail_grade(scored_d):
    results = find_safe_yields([scored_d], min_grade=SafetyGrade.A)
    assert results == []


def test_find_safe_yields_min_grade_a_only_returns_a(scored_a, scored_b, scored_d):
    results = find_safe_yields([scored_a, scored_b, scored_d], min_grade=SafetyGrade.A)
    assert all(sv.grade == SafetyGrade.A for sv in results)


def test_find_safe_yields_min_grade_f_returns_all_rated(scored_a, scored_b, scored_d):
    results = find_safe_yields([scored_a, scored_b, scored_d], min_grade=SafetyGrade.F)
    assert len(results) == 3


def test_find_safe_yields_returns_scored_vault_objects(scored_a, scored_b):
    results = find_safe_yields([scored_a, scored_b], min_grade=SafetyGrade.B)
    for r in results:
        assert isinstance(r, ScoredVault)
        assert hasattr(r, "vault")
        assert hasattr(r, "grade")
        assert hasattr(r, "score")
