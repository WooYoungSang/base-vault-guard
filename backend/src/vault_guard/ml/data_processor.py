"""Process raw collected vault data into ML training features."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from vault_guard.ml.data_collector import (
    CollectedVault,
    compute_max_drawdown,
    compute_tvl_change_7d,
)
from vault_guard.ml.data_generator import FEATURE_NAMES, _add_derived

logger = logging.getLogger(__name__)


def _estimate_utilization(vault: CollectedVault) -> float:
    """Estimate utilization from available data."""
    if vault.utilization is not None:
        return vault.utilization

    # Heuristic: higher APY lending pools tend to have higher utilization
    # This is a rough approximation when on-chain reads aren't available
    apy = vault.apy
    if apy <= 0:
        return 0.5  # default

    protocol = vault.protocol
    if protocol in ("aave-v3", "compound-v3"):
        # Lending protocols: APY correlates with utilization
        # Typical base rate ~2%, slope increases with utilization
        # Very rough: utilization ~ min(apy / 15, 0.95)
        return min(max(apy / 15.0, 0.05), 0.95)
    elif protocol in ("morpho", "morpho-v1"):
        return min(max(apy / 12.0, 0.05), 0.95)
    else:
        # AMM/DEX: utilization concept is different, use moderate default
        return 0.5


def _estimate_oracle_risk(vault: CollectedVault) -> float:
    """
    Estimate oracle risk score based on asset type and protocol.

    Lower is safer. Stablecoins and major assets get low scores.
    """
    symbol = vault.symbol.upper()

    # Stablecoin pairs are lower risk
    stables = {"USDC", "USDT", "DAI", "FRAX", "LUSD", "CUSD"}
    major = {"WETH", "ETH", "WBTC", "BTC", "CBETH", "CBBTC", "RETH", "WSTETH"}

    tokens = set(symbol.replace("/", "-").replace(" ", "-").split("-"))

    stable_count = len(tokens & stables)
    major_count = len(tokens & major)

    if stable_count == len(tokens) and len(tokens) > 0:
        return 0.05  # pure stablecoin
    elif stable_count > 0 or major_count > 0:
        return 0.15  # major asset
    else:
        return 0.40  # exotic/unknown token


def _assign_label(row: pd.Series) -> int:
    """
    Assign a grade label (0=A to 4=F) based on rule-based scoring.

    This bootstraps labels from feature values for initial training.
    """
    # Compute a simplified risk score (0-100, higher = safer)
    utilization_penalty = row["utilization"] * 25  # 0-25
    tvl_penalty = max(-row["tvl_change_7d"], 0) * 30  # 0-30 for negative changes
    oracle_penalty = row["oracle_risk_score"] * 15  # 0-15
    audit_bonus = row["audit_score"] * 20  # 0-20
    drawdown_penalty = row["drawdown_max"] * 20  # 0-20

    score = (
        100 - utilization_penalty - tvl_penalty - oracle_penalty
        - drawdown_penalty + audit_bonus
    )
    score = max(0, min(100, score))

    # Add noise to avoid perfectly deterministic labels
    if score >= 85:
        return 0  # A
    elif score >= 70:
        return 1  # B
    elif score >= 55:
        return 2  # C
    elif score >= 35:
        return 3  # D
    else:
        return 4  # F


def process_vaults(vaults: list[CollectedVault]) -> pd.DataFrame:
    """
    Convert collected vault data into ML feature DataFrame.

    Returns DataFrame with columns matching FEATURE_NAMES plus 'label',
    'protocol', 'symbol', and 'pool_id' for reference.
    """
    rows: list[dict] = []

    for vault in vaults:
        utilization = _estimate_utilization(vault)
        tvl_change_7d = compute_tvl_change_7d(vault.tvl_history)
        oracle_risk = _estimate_oracle_risk(vault)
        drawdown = compute_max_drawdown(vault.tvl_history)

        rows.append({
            "pool_id": vault.pool_id,
            "protocol": vault.protocol,
            "symbol": vault.symbol,
            "tvl_usd": vault.tvl_usd,
            "utilization": np.clip(utilization, 0.0, 1.0),
            "tvl_change_7d": np.clip(tvl_change_7d, -1.0, 1.0),
            "oracle_risk_score": np.clip(oracle_risk, 0.0, 1.0),
            "audit_score": np.clip(vault.audit_score, 0.0, 1.0),
            "drawdown_max": np.clip(drawdown, 0.0, 1.0),
        })

    if not rows:
        logger.warning("No vaults to process")
        return pd.DataFrame(columns=FEATURE_NAMES + ["label", "protocol", "symbol", "pool_id"])

    df = pd.DataFrame(rows)

    # Add derived features
    df = _add_derived(df)

    # Assign labels
    df["label"] = df.apply(_assign_label, axis=1)

    logger.info(
        "Processed %d vaults. Label distribution: %s",
        len(df),
        df["label"].value_counts().to_dict(),
    )
    return df


def save_training_data(df: pd.DataFrame, output_path: Path) -> Path:
    """Save processed training data to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save only feature columns + label for training
    feature_cols = FEATURE_NAMES + ["label"]
    meta_cols = ["pool_id", "protocol", "symbol", "tvl_usd"]
    save_cols = [c for c in meta_cols + feature_cols if c in df.columns]

    df[save_cols].to_csv(output_path, index=False)
    logger.info("Training data saved to %s (%d rows)", output_path, len(df))
    return output_path
