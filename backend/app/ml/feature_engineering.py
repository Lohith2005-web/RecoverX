import pandas as pd
import numpy as np
from typing import Tuple, List, Dict, Any
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Pre-action features known BEFORE recovery action
NUMERICAL_FEATURES = [
    "amount",
    "retry_count",
    "customer_historical_success_rate",
    "latency_ms",
    "risk_score",
    "hour_of_day",
    "day_of_week"
]

CATEGORICAL_FEATURES = [
    "payment_method",
    "gateway_id",
    "issuer_id",
    "failure_category",
    "failure_code",
    "subscription_flag",
    "device_type"
]

# Strict forbidden post-action fields (MUST NOT be used as ML features)
FORBIDDEN_FIELDS = [
    "status",
    "recovered_amount",
    "is_recoverable_ground_truth",
    "final_outcome",
    "outcome_status",
    "actual_recovered_amount",
    "recovery_cost",
    "net_recovered_amount"
]

def validate_no_data_leakage(df: pd.DataFrame) -> None:
    """
    Validates that no forbidden post-action or target leakage fields are present in the feature matrix.
    Raises ValueError if any leak is detected.
    """
    leaked_cols = [col for col in df.columns if col in FORBIDDEN_FIELDS]
    if leaked_cols:
        raise ValueError(
            f"DATA LEAKAGE DETECTED! The feature set contains forbidden post-action/target fields: {leaked_cols}. "
            "Model training must only use pre-action features available before recovery execution."
        )

def extract_features_and_target(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Processes transaction DataFrame, extracts time features, validates against data leakage,
    and returns feature DataFrame X and target Series y.
    """
    if "is_recoverable_ground_truth" not in df.columns:
        raise ValueError("Ground truth target column 'is_recoverable_ground_truth' not found in DataFrame.")

    # Extract time features from timestamp if present
    df = df.copy()
    if "timestamp" in df.columns:
        timestamps = pd.to_datetime(df["timestamp"])
        df["hour_of_day"] = timestamps.dt.hour
        df["day_of_week"] = timestamps.dt.dayofweek
    else:
        if "hour_of_day" not in df.columns:
            df["hour_of_day"] = 12
        if "day_of_week" not in df.columns:
            df["day_of_week"] = 0

    # Ensure subscription_flag is string/bool compatible
    df["subscription_flag"] = df["subscription_flag"].astype(str)

    y = df["is_recoverable_ground_truth"].astype(int)

    # Filter to pre-action features only
    all_feature_cols = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
    X = df[all_feature_cols].copy()

    # Perform strict leakage validation
    validate_no_data_leakage(X)

    return X, y

def build_preprocessor() -> ColumnTransformer:
    """
    Constructs a Scikit-Learn ColumnTransformer pipeline for pre-action features.
    Categorical features: OneHotEncoder(handle_unknown='ignore')
    Numerical features: StandardScaler()
    """
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERICAL_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES)
        ],
        remainder="drop"
    )
    return preprocessor
