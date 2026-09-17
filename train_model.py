"""Train a time-aware Random Forest for 7-day pump-failure risk."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, precision_score, recall_score, f1_score, roc_auc_score

import config
from data_loader import load_all_data, load_raw_history
from feature_engineering import FEATURE_COLS, add_features
from predictive_target import add_failure_target

MODEL_VERSION = "2.1"
TARGET_COL = "Failure_Next_7D"


def _time_split(df, test_fraction=0.2):
    dates = sorted(df["Date"].drop_duplicates())
    if len(dates) < 2:
        raise ValueError("At least two distinct dates are required for a time split")
    cutoff_index = max(1, int(len(dates) * (1 - test_fraction)))
    if cutoff_index >= len(dates):
        cutoff_index = len(dates) - 1
    cutoff = dates[cutoff_index]
    train = df[df["Date"] < cutoff].copy()
    test = df[df["Date"] >= cutoff].copy()
    return train, test, cutoff


def prepare_training_data(df):
    featured = add_features(df)
    featured = add_failure_target(featured, horizon_days=7)
    # First seven days have incomplete lag features; final seven days may have
    # unknown targets. Neither should enter supervised training.
    usable = featured.dropna(subset=FEATURE_COLS + [TARGET_COL]).copy()
    usable[TARGET_COL] = usable[TARGET_COL].astype(int)
    return usable


def train():
    df = load_raw_history()
    if df.empty:
        df = load_all_data()
    if df.empty:
        raise ValueError("No production data available for training")

    dataset = prepare_training_data(df)
    if dataset.empty:
        raise ValueError("No rows remain after feature/target preparation")
    if dataset[TARGET_COL].nunique() < 2:
        raise ValueError("Training target contains only one class; more failure/normal history is required")

    train_df, test_df, cutoff = _time_split(dataset)
    if train_df[TARGET_COL].nunique() < 2:
        raise ValueError("Training period contains only one target class; choose a later cutoff or add more history")

    X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET_COL]
    X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET_COL]

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    print("\n=== Time-aware evaluation ===")
    print(f"Train rows: {len(train_df)} | Test rows: {len(test_df)}")
    print(f"Time cutoff: {cutoff.date()}")
    print(classification_report(y_test, y_pred, zero_division=0))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, y_pred))

    metrics = {
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_prob)) if y_test.nunique() == 2 else None,
    }
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall:    {metrics['recall']:.3f}")
    print(f"F1:        {metrics['f1']:.3f}")
    print(f"ROC-AUC:   {metrics['roc_auc']:.3f}" if metrics['roc_auc'] is not None else "ROC-AUC:   unavailable (one test class)")

    # Store training medians as the reference point for local explanations.
    feature_baseline = {col: float(X_train[col].median()) for col in FEATURE_COLS}

    artifact = {
        "model": model,
        "feature_cols": FEATURE_COLS,
        "target": TARGET_COL,
        "horizon_days": 7,
        "model_version": MODEL_VERSION,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "time_cutoff": cutoff.strftime("%Y-%m-%d"),
        "metrics": metrics,
        "feature_baseline": feature_baseline,
    }

    os.makedirs(os.path.dirname(config.MODEL_PATH) or ".", exist_ok=True)
    joblib.dump(artifact, config.MODEL_PATH)
    print(f"Model saved to {config.MODEL_PATH}")
    return model, metrics


# Backward-compatible alias for older tests/callers.
def train_model():
    return train()


if __name__ == "__main__":
    train()
