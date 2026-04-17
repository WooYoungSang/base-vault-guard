"""XGBoost model trainer for Vault Guard safety scoring."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from vault_guard.ml.data_generator import (
    FEATURE_NAMES,
    GRADE_LABELS,
    generate_training_data,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = Path(__file__).parent / "models"
DEFAULT_MODEL_PATH = DEFAULT_MODEL_DIR / "vault_guard_model.json"
DEFAULT_META_PATH = DEFAULT_MODEL_DIR / "feature_metadata.json"


def train_model(
    n_samples: int = 2500,
    seed: int = 42,
    test_size: float = 0.20,
    save_dir: Path | None = None,
) -> dict:
    """
    Train an XGBoost multi-class classifier on synthetic vault risk data.

    Returns a dict with metrics: accuracy, macro_auc, per_class_report.
    """
    if save_dir is None:
        save_dir = DEFAULT_MODEL_DIR
    save_dir.mkdir(parents=True, exist_ok=True)

    model_path = save_dir / "vault_guard_model.json"
    meta_path = save_dir / "feature_metadata.json"

    # Generate data
    X, y = generate_training_data(n_samples=n_samples, seed=seed)

    # Stratified split
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

    # Evaluate
    probs = booster.predict(dtest)
    preds = np.argmax(probs, axis=1)

    accuracy = float(accuracy_score(y_test, preds))
    report = classification_report(y_test, preds, target_names=GRADE_LABELS, output_dict=True)

    # Macro AUC (one-vs-rest)
    try:
        macro_auc = float(roc_auc_score(
            y_test, probs, multi_class="ovr", average="macro",
        ))
    except ValueError:
        macro_auc = 0.0

    # Save model
    booster.save_model(str(model_path))
    logger.info("Model saved to %s", model_path)

    # Save feature metadata
    importance = booster.get_score(importance_type="gain")
    metadata = {
        "feature_names": FEATURE_NAMES,
        "grade_labels": GRADE_LABELS,
        "n_training_samples": len(y_train),
        "n_test_samples": len(y_test),
        "accuracy": accuracy,
        "macro_auc": macro_auc,
        "feature_importance": importance,
    }
    meta_path.write_text(json.dumps(metadata, indent=2))
    logger.info("Metadata saved to %s", meta_path)

    return {
        "accuracy": accuracy,
        "macro_auc": macro_auc,
        "per_class_report": report,
        "model_path": str(model_path),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    metrics = train_model()
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Macro AUC: {metrics['macro_auc']:.4f}")
    for grade in GRADE_LABELS:
        info = metrics["per_class_report"][grade]
        print(f"  {grade}: precision={info['precision']:.3f} recall={info['recall']:.3f}")
