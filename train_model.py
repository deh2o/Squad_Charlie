"""
train_model.py
Member 2 (ML Engineer) | Tuesday deliverable.

Trains a RandomForestClassifier on production_data to predict
Pump_Status (0=Normal, 1=Failure), evaluates it, and saves it as
pump_failure_model.pkl for predict.py to load.
"""

import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

from data_loader import load_all_data
from config import MODEL_PATH

FEATURE_COLS = ['Oil_Rate', 'Water_Cut', 'Pressure', 'Temperature']


def train():
    # 1. Load
    df = load_all_data()

    # 2. Features (X) and target (y)
    X = df[FEATURE_COLS]
    y = df['Pump_Status']

    # 3. Train/test split (80/20) — stratify keeps the same failure
    #    ratio in both splits, critical with imbalanced data (~15% failures)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # 4. Train
    model = RandomForestClassifier(
        n_estimators=100,  # 100 trees vote on the outcome
        max_depth=5,  # keeps individual trees shallow -> less overfitting
        random_state=42,  # reproducible results
    )
    model.fit(X_train, y_train)

    # 5. Evaluate
    y_prob = model.predict_proba(X_test)[:, 1]
    print(classification_report(y_test, model.predict(X_test)))
    auc = roc_auc_score(y_test, y_prob)
    print(f"AUC: {auc:.3f}")  # 0.5 = random guessing, 1.0 = perfect; aim for > 0.85

    # 6. Save
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    return model, auc


if __name__ == "__main__":
    train()