"""Safe Yield Finder — filter by safety grade, rank by APY."""

from __future__ import annotations

from vault_guard.models import SafetyGrade, ScoredVault

# Grade ordering: A is safest, F is least safe
_GRADE_ORDER = [SafetyGrade.A, SafetyGrade.B, SafetyGrade.C, SafetyGrade.D, SafetyGrade.F]


def _grade_rank(grade: SafetyGrade) -> int:
    """Lower rank = safer (A=0, B=1, …, F=4, UNRATED=99)."""
    try:
        return _GRADE_ORDER.index(grade)
    except ValueError:
        return 99  # UNRATED sorts last


def find_safe_yields(
    scored_vaults: list[ScoredVault],
    min_grade: SafetyGrade = SafetyGrade.B,
) -> list[ScoredVault]:
    """
    Filter vaults by minimum safety grade and sort by APY descending.

    UNRATED vaults are always excluded.
    """
    min_rank = _grade_rank(min_grade)
    eligible = [
        sv for sv in scored_vaults
        if sv.grade != SafetyGrade.UNRATED and _grade_rank(sv.grade) <= min_rank
    ]
    return sorted(eligible, key=lambda sv: sv.vault.apy, reverse=True)
