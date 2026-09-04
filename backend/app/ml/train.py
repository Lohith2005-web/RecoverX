import os
import sys
import time
import json
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    accuracy_score,
    confusion_matrix
)
from xgboost import XGBClassifier

# Auto-add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.db.models import Transaction
from app.simulator.generator import seed_database
from app.ml.feature_engineering import (
    extract_features_and_target,
    build_preprocessor,
    validate_no_data_leakage,
    NUMERICAL_FEATURES,
    CATEGORICAL_FEATURES,
    FORBIDDEN_FIELDS
)
from app.ml.baseline import NaiveRetryBaseline

MODEL_DIR = Path(__file__).resolve().parent / "models"

def train_recoverability_model(seed: int = 42) -> Dict[str, Any]:
    """
    Trains the primary XGBoost Recoverability Classification Model on failed transaction data.
    Saves model artifacts and evaluation metrics to disk.
    """
    start_time = time.time()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Fetch transaction dataset from database
    db = SessionLocal()
    try:
        txns = db.query(Transaction).filter(Transaction.status == "FAILED").all()
        if len(txns) < 500:
            print("Insufficient failed transactions in DB. Seeding dataset (seed 42)...")
            seed_database(db, num_transactions=50000, seed=seed)
            txns = db.query(Transaction).filter(Transaction.status == "FAILED").all()

        print(f"Loaded {len(txns)} failed transactions for ML model training.")

        # Convert to pandas DataFrame
        txn_dicts = []
        for t in txns:
            txn_dicts.append({
                "id": t.id,
                "amount": t.amount,
                "retry_count": t.retry_count,
                "customer_historical_success_rate": t.customer_historical_success_rate,
                "latency_ms": t.latency_ms,
                "risk_score": t.risk_score,
                "payment_method": t.payment_method,
                "gateway_id": t.gateway_id,
                "issuer_id": t.issuer_id,
                "failure_category": t.failure_category,
                "failure_code": t.failure_code,
                "subscription_flag": t.subscription_flag,
                "device_type": t.device_type,
                "country": t.country,
                "timestamp": t.timestamp,
                "is_recoverable_ground_truth": t.is_recoverable_ground_truth
            })
    finally:
        db.close()

    df = pd.DataFrame(txn_dicts)

    # 2. Extract pre-action features & target label
    X, y = extract_features_and_target(df)
    validate_no_data_leakage(X)

    # 3. Train / Test Split (80% Train, 20% Test, Stratified)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=seed, stratify=y
    )

    # 4. Build Pipeline (Preprocessor + XGBoost Classifier)
    preprocessor = build_preprocessor()
    xgb_model = XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=seed,
        eval_metric="logloss"
    )

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", xgb_model)
    ])

    # 5. Fit model ONLY on training data
    pipeline.fit(X_train, y_train)
    training_duration = round(time.time() - start_time, 3)

    # 6. Evaluate on untouched test set
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    roc_auc = roc_auc_score(y_test, y_proba)
    acc = accuracy_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred).tolist()

    # 7. Evaluate Naive Baseline Model for comparison
    baseline_model = NaiveRetryBaseline()
    baseline_metrics = baseline_model.evaluate(X_test, y_test)

    # 8. Compute Feature Importances
    preproc_fitted = pipeline.named_steps["preprocessor"]
    cat_feature_names = preproc_fitted.named_transformers_["cat"].get_feature_names_out(CATEGORICAL_FEATURES).tolist()
    feature_names = NUMERICAL_FEATURES + cat_feature_names
    importances = xgb_model.feature_importances_

    feature_importance_list = []
    for f_name, imp in zip(feature_names, importances):
        feature_importance_list.append({
            "feature": f_name,
            "importance": round(float(imp), 4)
        })
    feature_importance_list.sort(key=lambda x: x["importance"], reverse=True)

    # 9. Save Model Artifact and Metrics
    model_filepath = MODEL_DIR / "recoverability_model.joblib"
    joblib.dump(pipeline, model_filepath)

    evaluation_report = {
        "model_type": "XGBoost Classifier",
        "seed_used": seed,
        "dataset_size": len(df),
        "failed_transactions_count": len(df),
        "target_distribution": {
            "total_positive_recoverable": int(y.sum()),
            "total_negative_unrecoverable": int((1 - y).sum()),
            "positive_class_ratio": round(float(y.mean()), 4)
        },
        "train_size": len(X_train),
        "test_size": len(X_test),
        "training_duration_seconds": training_duration,
        "test_metrics": {
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1_score": round(float(f1), 4),
            "roc_auc": round(float(roc_auc), 4),
            "accuracy": round(float(acc), 4),
            "confusion_matrix": cm
        },
        "baseline_comparison": baseline_metrics,
        "feature_importances": feature_importance_list[:15], # Top 15 features
        "excluded_forbidden_fields": FORBIDDEN_FIELDS,
        "model_file_path": "backend/app/ml/models/recoverability_model.joblib"
    }

    report_filepath = MODEL_DIR / "evaluation_results.json"
    with open(report_filepath, "w", encoding="utf-8") as f:
        json.dump(evaluation_report, f, indent=2)

    print("Model training complete.")
    print(f"Test Set Metrics -> Precision: {prec:.4f}, Recall: {rec:.4f}, F1: {f1:.4f}, ROC-AUC: {roc_auc:.4f}")
    return evaluation_report

if __name__ == "__main__":
    train_recoverability_model()
