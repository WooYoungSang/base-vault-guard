"""Synthetic training data generator for DeFi vault risk classification."""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_NAMES = [
    "utilization",
    "tvl_change_7d",
    "oracle_risk_score",
    "audit_score",
    "drawdown_max",
    "utilization_squared",
    "risk_composite",
]

GRADE_MAP = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}
GRADE_LABELS = ["A", "B", "C", "D", "F"]


def _clip01(arr: np.ndarray) -> np.ndarray:
    return np.clip(arr, 0.0, 1.0)


def _add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features: utilization_squared, risk_composite."""
    df["utilization_squared"] = df["utilization"] ** 2
    df["risk_composite"] = (
        df["oracle_risk_score"] * 0.4
        + (1.0 - df["audit_score"]) * 0.3
        + df["drawdown_max"] * 0.3
    )
    return df


def generate_training_data(
    n_samples: int = 2500,
    seed: int = 42,
) -> tuple[pd.DataFrame, np.ndarray]:
    """
    Generate synthetic DeFi vault risk data with grade labels.

    Returns (features_df, labels) where labels are ints 0-4 mapping to A-F.
    """
    rng = np.random.default_rng(seed)

    samples_per_grade = {
        "A": int(n_samples * 0.20),
        "B": int(n_samples * 0.25),
        "C": int(n_samples * 0.25),
        "D": int(n_samples * 0.18),
        "F": int(n_samples * 0.12),
    }

    all_rows: list[dict] = []
    all_labels: list[int] = []

    # --- Grade A: safe vaults ---
    n = samples_per_grade["A"]
    rows_a = {
        "utilization": _clip01(rng.normal(0.35, 0.15, n)),
        "tvl_change_7d": np.clip(rng.normal(0.05, 0.08, n), -0.15, 0.50),
        "oracle_risk_score": _clip01(rng.normal(0.08, 0.06, n)),
        "audit_score": _clip01(rng.normal(0.95, 0.04, n)),
        "drawdown_max": _clip01(rng.normal(0.02, 0.02, n)),
    }
    for i in range(n):
        all_rows.append({k: float(v[i]) for k, v in rows_a.items()})
        all_labels.append(GRADE_MAP["A"])

    # --- Grade B: good vaults ---
    n = samples_per_grade["B"]
    rows_b = {
        "utilization": _clip01(rng.normal(0.50, 0.15, n)),
        "tvl_change_7d": np.clip(rng.normal(0.02, 0.10, n), -0.20, 0.40),
        "oracle_risk_score": _clip01(rng.normal(0.15, 0.08, n)),
        "audit_score": _clip01(rng.normal(0.85, 0.08, n)),
        "drawdown_max": _clip01(rng.normal(0.06, 0.04, n)),
    }
    for i in range(n):
        all_rows.append({k: float(v[i]) for k, v in rows_b.items()})
        all_labels.append(GRADE_MAP["B"])

    # --- Grade C: moderate risk ---
    n = samples_per_grade["C"]
    rows_c = {
        "utilization": _clip01(rng.normal(0.72, 0.10, n)),
        "tvl_change_7d": np.clip(rng.normal(-0.05, 0.12, n), -0.30, 0.30),
        "oracle_risk_score": _clip01(rng.normal(0.35, 0.12, n)),
        "audit_score": _clip01(rng.normal(0.65, 0.12, n)),
        "drawdown_max": _clip01(rng.normal(0.15, 0.08, n)),
    }
    for i in range(n):
        all_rows.append({k: float(v[i]) for k, v in rows_c.items()})
        all_labels.append(GRADE_MAP["C"])

    # --- Grade D: high risk ---
    n = samples_per_grade["D"]
    rows_d = {
        "utilization": _clip01(rng.normal(0.85, 0.08, n)),
        "tvl_change_7d": np.clip(rng.normal(-0.18, 0.10, n), -0.50, 0.10),
        "oracle_risk_score": _clip01(rng.normal(0.60, 0.15, n)),
        "audit_score": _clip01(rng.normal(0.35, 0.15, n)),
        "drawdown_max": _clip01(rng.normal(0.35, 0.12, n)),
    }
    for i in range(n):
        all_rows.append({k: float(v[i]) for k, v in rows_d.items()})
        all_labels.append(GRADE_MAP["D"])

    # --- Grade F: dangerous ---
    n = samples_per_grade["F"]
    rows_f = {
        "utilization": _clip01(rng.normal(0.93, 0.05, n)),
        "tvl_change_7d": np.clip(rng.normal(-0.30, 0.12, n), -0.80, 0.05),
        "oracle_risk_score": _clip01(rng.normal(0.80, 0.12, n)),
        "audit_score": _clip01(rng.normal(0.15, 0.10, n)),
        "drawdown_max": _clip01(rng.normal(0.55, 0.15, n)),
    }
    for i in range(n):
        all_rows.append({k: float(v[i]) for k, v in rows_f.items()})
        all_labels.append(GRADE_MAP["F"])

    # --- Edge cases: new vaults with extreme values ---
    edge_cases = [
        # Flash-crash recovery: high drawdown but recovering TVL
        {"utilization": 0.45, "tvl_change_7d": 0.15, "oracle_risk_score": 0.20,
         "audit_score": 0.90, "drawdown_max": 0.40},
        # New vault: no drawdown history, moderate everything
        {"utilization": 0.50, "tvl_change_7d": 0.0, "oracle_risk_score": 0.30,
         "audit_score": 0.70, "drawdown_max": 0.0},
        # Perfect vault
        {"utilization": 0.10, "tvl_change_7d": 0.10, "oracle_risk_score": 0.01,
         "audit_score": 1.0, "drawdown_max": 0.0},
        # Worst vault
        {"utilization": 1.0, "tvl_change_7d": -0.50, "oracle_risk_score": 1.0,
         "audit_score": 0.0, "drawdown_max": 1.0},
    ]
    edge_labels = [GRADE_MAP["B"], GRADE_MAP["C"], GRADE_MAP["A"], GRADE_MAP["F"]]

    all_rows.extend(edge_cases)
    all_labels.extend(edge_labels)

    df = pd.DataFrame(all_rows)
    df = _add_derived(df)
    labels = np.array(all_labels, dtype=np.int32)

    return df, labels
