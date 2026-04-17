"""CLI entrypoint: collect real vault data and save for ML training."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from vault_guard.ml.data_collector import collect_all, save_raw_data
from vault_guard.ml.data_processor import process_vaults, save_training_data

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
TRAINING_CSV = DATA_DIR / "vault_training_data.csv"


async def run_collection() -> None:
    """Run the full collection pipeline."""
    start = datetime.now(tz=timezone.utc)
    print(f"[{start:%Y-%m-%d %H:%M:%S UTC}] Starting vault data collection...")

    # Step 1: Collect raw data from APIs
    print("  Fetching data from DeFiLlama...")
    vaults = await collect_all(skip_onchain=True)

    if not vaults:
        print("  WARNING: No vaults collected. Check network connectivity.")
        sys.exit(1)

    print(f"  Collected {len(vaults)} vaults from {len(set(v.protocol for v in vaults))} protocols")

    # Step 2: Save raw data
    raw_path = await save_raw_data(vaults, RAW_DIR)
    print(f"  Raw data saved to {raw_path}")

    # Step 3: Process into ML features
    print("  Processing into ML features...")
    df = process_vaults(vaults)

    if df.empty:
        print("  WARNING: Processing produced no rows.")
        sys.exit(1)

    # Step 4: Save training CSV
    csv_path = save_training_data(df, TRAINING_CSV)
    print(f"  Training data saved to {csv_path}")

    # Step 5: Print summary
    end = datetime.now(tz=timezone.utc)
    elapsed = (end - start).total_seconds()

    print()
    print("=" * 60)
    print("Collection Summary")
    print("=" * 60)
    print(f"  Vaults collected:    {len(vaults)}")
    print(f"  Training rows:       {len(df)}")
    print(f"  Protocols:           {', '.join(sorted(df['protocol'].unique()))}")
    print(f"  Symbols:             {df['symbol'].nunique()} unique")

    # Data completeness
    feature_cols = [
        "utilization", "tvl_change_7d", "oracle_risk_score",
        "audit_score", "drawdown_max",
    ]
    completeness = {col: (df[col].notna().sum() / len(df) * 100) for col in feature_cols}
    print("  Data completeness:")
    for col, pct in completeness.items():
        print(f"    {col:25s} {pct:5.1f}%")

    # Label distribution
    label_map = {0: "A", 1: "B", 2: "C", 3: "D", 4: "F"}
    print("  Label distribution:")
    for label_val, count in sorted(df["label"].value_counts().items()):
        grade = label_map.get(label_val, "?")
        print(f"    Grade {grade}: {count:4d} ({count / len(df) * 100:5.1f}%)")

    print(f"  Collection time:     {elapsed:.1f}s")
    print(f"  Timestamp:           {end:%Y-%m-%d %H:%M:%S UTC}")
    print("=" * 60)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    asyncio.run(run_collection())


if __name__ == "__main__":
    main()
