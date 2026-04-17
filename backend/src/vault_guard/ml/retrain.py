"""Retrain Vault Guard ML model using real collected data."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from vault_guard.ml.data_generator import (
    FEATURE_NAMES,
    GRADE_LABELS,
    generate_training_data,
)
from vault_guard.ml.trainer import DEFAULT_MODEL_DIR

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
TRAINING_CSV = DATA_DIR / "vault_training_data.csv"

MIN_REAL_SAMPLES = 200


def load_real_data(csv_path: Path = TRAINING_CSV) -> tuple[pd.DataFrame, np.ndarray] | None:
    """Load real training data from CSV."""
    if not csv_path.exists():
        logger.warning("Training CSV not found: %s", csv_path)
        return None

    df = pd.read_csv(csv_path)
    required = FEATURE_NAMES + ["label"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.warning("CSV missing columns: %s", missing)
        return None

    X = df[FEATURE_NAMES]
    y = df["label"].values.astype(np.int32)

    logger.info("Loaded %d real samples from %s", len(X), csv_path)
    return X, y


def _train_and_evaluate(
    X: pd.DataFrame,
    y: np.ndarray,
    seed: int = 42,
    test_size: float = 0.20,
    label: str = "model",
) -> dict:
    """Train XGBoost and return metrics dict."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y,
    )

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_NAMES)
    dtest = xgb.DMatrix(X_test, label=y_test, feature_names=FEATURE_NAMES)

    params = {
        "objective": "multi:softprob",
        "num_class": len(GRADE_LABELS),
        "max_depth": 5,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "eval_metric": "mlogloss",
        "nthread": 1,
        "seed": seed,
    }

    booster = xgb.train(
        params,
        dtrain,
        num_boost_round=150,
        evals=[(dtest, "test")],
        verbose_eval=False,
    )

    probs = booster.predict(dtest)
    preds = np.argmax(probs, axis=1)

    accuracy = float(accuracy_score(y_test, preds))

    try:
        macro_auc = float(roc_auc_score(
            y_test, probs, multi_class="ovr", average="macro",
        ))
    except ValueError:
        macro_auc = 0.0

    report = classification_report(y_test, preds, target_names=GRADE_LABELS, output_dict=True)

    return {
        "label": label,
        "accuracy": accuracy,
        "macro_auc": macro_auc,
        "per_class_report": report,
        "booster": booster,
        "n_train": len(y_train),
        "n_test": len(y_test),
    }


def retrain(
    csv_path: Path = TRAINING_CSV,
    save_dir: Path | None = None,
    seed: int = 42,
    synthetic_samples: int = 2500,
) -> dict:
    """
    Retrain model using real data, augmented with synthetic if needed.

    Returns dict with metrics for both synthetic-only and real-data models.
    """
    if save_dir is None:
        save_dir = DEFAULT_MODEL_DIR
    save_dir.mkdir(parents=True, exist_ok=True)

    results: dict = {}

    # Step 1: Train synthetic-only baseline
    print("Training synthetic-only baseline...")
    X_syn, y_syn = generate_training_data(n_samples=synthetic_samples, seed=seed)
    syn_metrics = _train_and_evaluate(X_syn, y_syn, seed=seed, label="synthetic-only")
    results["synthetic"] = {
        "accuracy": syn_metrics["accuracy"],
        "macro_auc": syn_metrics["macro_auc"],
        "n_samples": syn_metrics["n_train"] + syn_metrics["n_test"],
    }

    # Step 2: Load real data
    real = load_real_data(csv_path)
    if real is None:
        print("No real data available. Using synthetic-only model.")
        _save_model(syn_metrics["booster"], save_dir, syn_metrics)
        results["model_used"] = "synthetic-only"
        return results

    X_real, y_real = real
    print(f"Real data: {len(X_real)} samples")

    # Step 3: Augment with synthetic if needed
    if len(X_real) < MIN_REAL_SAMPLES:
        print(
            f"Real data ({len(X_real)}) below threshold ({MIN_REAL_SAMPLES}), "
            f"augmenting with synthetic data..."
        )
        augment_n = max(synthetic_samples - len(X_real), MIN_REAL_SAMPLES)
        X_aug, y_aug = generate_training_data(n_samples=augment_n, seed=seed)
        X_combined = pd.concat([X_real, X_aug], ignore_index=True)
        y_combined = np.concatenate([y_real, y_aug])
        data_label = f"real({len(X_real)})+synthetic({len(X_aug)})"
    else:
        X_combined = X_real
        y_combined = y_real
        data_label = f"real-only({len(X_real)})"

    # Step 4: Ensure all grade classes are represented
    unique_labels = set(y_combined.tolist())
    if len(unique_labels) < len(GRADE_LABELS):
        missing = set(range(len(GRADE_LABELS))) - unique_labels
        print(f"Missing grade classes: {[GRADE_LABELS[m] for m in missing]}, adding synthetic fill")
        X_fill, y_fill = generate_training_data(n_samples=500, seed=seed + 1)
        X_combined = pd.concat([X_combined, X_fill], ignore_index=True)
        y_combined = np.concatenate([y_combined, y_fill])
        data_label += "+fill"

    # Step 5: Train real-data model
    print(f"Training model on {data_label}...")
    real_metrics = _train_and_evaluate(
        X_combined, y_combined, seed=seed, label=data_label,
    )
    results["real_data"] = {
        "accuracy": real_metrics["accuracy"],
        "macro_auc": real_metrics["macro_auc"],
        "n_samples": real_metrics["n_train"] + real_metrics["n_test"],
        "composition": data_label,
    }

    # Step 6: Save the better model
    if real_metrics["accuracy"] >= syn_metrics["accuracy"] - 0.05:
        # Use real-data model unless it's significantly worse
        _save_model(real_metrics["booster"], save_dir, real_metrics)
        results["model_used"] = data_label
        print(f"Saved real-data model ({data_label})")
    else:
        _save_model(syn_metrics["booster"], save_dir, syn_metrics)
        results["model_used"] = "synthetic-only"
        print("Real-data model worse than synthetic; kept synthetic model")

    return results


def _save_model(booster: xgb.Booster, save_dir: Path, metrics: dict) -> None:
    """Save model and metadata."""
    model_path = save_dir / "vault_guard_model.json"
    meta_path = save_dir / "feature_metadata.json"

    booster.save_model(str(model_path))

    importance = booster.get_score(importance_type="gain")
    metadata = {
        "feature_names": FEATURE_NAMES,
        "grade_labels": GRADE_LABELS,
        "n_training_samples": metrics["n_train"],
        "n_test_samples": metrics["n_test"],
        "accuracy": metrics["accuracy"],
        "macro_auc": metrics["macro_auc"],
        "data_source": metrics["label"],
        "feature_importance": importance,
    }
    meta_path.write_text(json.dumps(metadata, indent=2))
    logger.info("Model saved to %s", model_path)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    results = retrain()

    print()
    print("=" * 60)
    print("Retrain Results")
    print("=" * 60)

    if "synthetic" in results:
        s = results["synthetic"]
        print(f"  Synthetic-only:  accuracy={s['accuracy']:.4f}  AUC={s['macro_auc']:.4f}  "
              f"n={s['n_samples']}")

    if "real_data" in results:
        r = results["real_data"]
        print(f"  Real data:       accuracy={r['accuracy']:.4f}  AUC={r['macro_auc']:.4f}  "
              f"n={r['n_samples']}  ({r['composition']})")

    print(f"  Model used:      {results.get('model_used', 'unknown')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
