import os
import json
import joblib
import datetime
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Union, List
from app.ml.feature_engineering import (
    NUMERICAL_FEATURES,
    CATEGORICAL_FEATURES,
    validate_no_data_leakage
)

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_FILE = MODEL_DIR / "recoverability_model.joblib"
EVALUATION_FILE = MODEL_DIR / "evaluation_results.json"

_MODEL_CACHE = None

def get_model():
    """
    Returns the loaded trained Scikit-Learn / XGBoost pipeline.
    Loads from disk cache, or triggers model training if model file is missing.
    """
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    if not MODEL_FILE.exists():
        print("Trained model artifact not found. Triggering automated model training...")
        from app.ml.train import train_recoverability_model
        train_recoverability_model()

    _MODEL_CACHE = joblib.load(MODEL_FILE)
    return _MODEL_CACHE

def reload_model():
    """
    Forces reload of the trained model from disk.
    """
    global _MODEL_CACHE
    _MODEL_CACHE = None
    return get_model()

def predict_recoverability(input_data: Union[Dict[str, Any], pd.DataFrame]) -> Dict[str, Any]:
    """
    Inference interface:
    Accepts pre-action features of a failed transaction and returns probability prediction.
    """
    if isinstance(input_data, dict):
        df_input = pd.DataFrame([input_data])
    else:
        df_input = input_data.copy()

    # Pre-process time features if timestamp provided
    if "timestamp" in df_input.columns:
        timestamps = pd.to_datetime(df_input["timestamp"])
        df_input["hour_of_day"] = timestamps.dt.hour
        df_input["day_of_week"] = timestamps.dt.dayofweek
    else:
        if "hour_of_day" not in df_input.columns:
            df_input["hour_of_day"] = 12
        if "day_of_week" not in df_input.columns:
            df_input["day_of_week"] = 0

    if "subscription_flag" in df_input.columns:
        df_input["subscription_flag"] = df_input["subscription_flag"].astype(str)

    # Validate against forbidden post-action fields
    validate_no_data_leakage(df_input)

    # Ensure all required features are present
    all_features = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
    for feat in all_features:
        if feat not in df_input.columns:
            raise ValueError(f"Missing required pre-action feature: '{feat}'")

    X_infer = df_input[all_features]

    pipeline = get_model()
    proba = pipeline.predict_proba(X_infer)[:, 1][0]

    return {
        "recoverability_probability": round(float(proba), 4),
        "model_version": "1.0.0",
        "prediction_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

def predict_recoverability_batch(input_data: Union[List[Dict[str, Any]], pd.DataFrame]) -> List[float]:
    """
    Batch inference interface:
    Accepts pre-action features for a batch of failed transactions and returns
    a list of recoverability probabilities rounded to 4 decimal places.
    """
    if isinstance(input_data, list):
        df_input = pd.DataFrame(input_data)
    else:
        df_input = input_data.copy()

    if df_input.empty:
        return []

    if "timestamp" in df_input.columns:
        timestamps = pd.to_datetime(df_input["timestamp"])
        df_input["hour_of_day"] = timestamps.dt.hour
        df_input["day_of_week"] = timestamps.dt.dayofweek
    else:
        if "hour_of_day" not in df_input.columns:
            df_input["hour_of_day"] = 12
        if "day_of_week" not in df_input.columns:
            df_input["day_of_week"] = 0

    if "subscription_flag" in df_input.columns:
        df_input["subscription_flag"] = df_input["subscription_flag"].astype(str)

    validate_no_data_leakage(df_input)

    all_features = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
    for feat in all_features:
        if feat not in df_input.columns:
            raise ValueError(f"Missing required pre-action feature: '{feat}'")

    X_infer = df_input[all_features]
    pipeline = get_model()
    probas = pipeline.predict_proba(X_infer)[:, 1]
    return [round(float(p), 4) for p in probas]


def get_evaluation_metrics() -> Dict[str, Any]:
    """
    Returns stored evaluation metrics report.
    """
    if not EVALUATION_FILE.exists():
        from app.ml.train import train_recoverability_model
        train_recoverability_model()

    with open(EVALUATION_FILE, "r", encoding="utf-8") as f:
        metrics = json.load(f)
    return metrics
