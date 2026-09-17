"""Local, model-agnostic explanations for pump-failure predictions."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _display_name(feature: str) -> str:
    return feature.replace("_", " ").replace("7D", "7-day").replace("1D", "1-day").replace("3D", "3-day")


def explain_prediction(model, row: pd.DataFrame, feature_cols: list[str],
                       baseline: pd.Series | None = None, top_n: int = 5) -> list[dict]:
    """Estimate per-feature contribution to the predicted failure probability.

    A feature's contribution is the change in predicted probability when that
    feature is replaced by a reference value (training median by default).
    Positive values increase predicted risk; negative values decrease it.
    """
    if row.empty:
        raise ValueError("Prediction row cannot be empty")
    if len(row) != 1:
        raise ValueError("Exactly one prediction row is required")

    x = row[feature_cols].iloc[0].astype(float)
    if baseline is None:
        baseline = x
    baseline = baseline.reindex(feature_cols).astype(float)

    current = float(model.predict_proba(pd.DataFrame([x], columns=feature_cols))[0, 1])
    explanations = []

    for feature in feature_cols:
        reference = baseline[feature]
        if pd.isna(reference) or pd.isna(x[feature]):
            continue
        if np.isclose(float(x[feature]), float(reference)):
            contribution = 0.0
        else:
            counterfactual = x.copy()
            counterfactual[feature] = reference
            counter_prob = float(
                model.predict_proba(pd.DataFrame([counterfactual], columns=feature_cols))[0, 1]
            )
            contribution = current - counter_prob

        explanations.append({
            "feature": feature,
            "name": _display_name(feature),
            "value": float(x[feature]),
            "baseline": float(reference),
            "contribution": float(contribution),
            "direction": "increases risk" if contribution > 0 else "decreases risk" if contribution < 0 else "neutral",
        })

    explanations.sort(key=lambda item: abs(item["contribution"]), reverse=True)
    return explanations[:top_n]
