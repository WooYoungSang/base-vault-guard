"""Historical Risk Tracker — SQLite storage for grade history per vault."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from vault_guard.models import SafetyGrade

_DEFAULT_DB = Path("data/vault_guard_history.db")

_DDL = """
CREATE TABLE IF NOT EXISTS grade_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vault_address TEXT NOT NULL,
    grade         TEXT NOT NULL,
    score         REAL NOT NULL,
    recorded_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gh_vault ON grade_history(vault_address);
CREATE INDEX IF NOT EXISTS idx_gh_time  ON grade_history(recorded_at);
"""


@dataclass
class GradeRecord:
    vault_address: str
    grade: SafetyGrade
    score: float
    recorded_at: datetime


@contextmanager
def _conn(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db(db_path: Path = _DEFAULT_DB) -> None:
    with _conn(db_path) as con:
        con.executescript(_DDL)


def record_grade(
    vault_address: str,
    grade: SafetyGrade,
    score: float,
    db_path: Path = _DEFAULT_DB,
) -> None:
    """Insert a new grade record for a vault."""
    now = datetime.now(timezone.utc).isoformat()
    with _conn(db_path) as con:
        con.execute(
            "INSERT INTO grade_history (vault_address, grade, score, recorded_at) VALUES (?,?,?,?)",
            (vault_address, grade.value, score, now),
        )


def get_history(
    vault_address: str,
    limit: int = 30,
    db_path: Path = _DEFAULT_DB,
) -> list[GradeRecord]:
    """Return the most recent grade records for a vault."""
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT * FROM grade_history WHERE vault_address=? ORDER BY recorded_at DESC LIMIT ?",
            (vault_address, limit),
        ).fetchall()
    return [
        GradeRecord(
            vault_address=r["vault_address"],
            grade=SafetyGrade(r["grade"]),
            score=r["score"],
            recorded_at=datetime.fromisoformat(r["recorded_at"]),
        )
        for r in rows
    ]


def detect_grade_drop(
    vault_address: str,
    db_path: Path = _DEFAULT_DB,
) -> bool:
    """
    Return True if the latest grade is 2+ tiers below the previous grade.
    Example: B → D triggers alert.
    """
    _GRADE_RANK = {
        SafetyGrade.A: 0,
        SafetyGrade.B: 1,
        SafetyGrade.C: 2,
        SafetyGrade.D: 3,
        SafetyGrade.F: 4,
        SafetyGrade.UNRATED: 99,
    }
    records = get_history(vault_address, limit=2, db_path=db_path)
    if len(records) < 2:
        return False
    latest_rank = _GRADE_RANK.get(records[0].grade, 99)
    prev_rank = _GRADE_RANK.get(records[1].grade, 99)
    return (latest_rank - prev_rank) >= 2
