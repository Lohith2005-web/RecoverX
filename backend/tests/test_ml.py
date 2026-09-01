import os
import pytest
import pandas as pd
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.ml.feature_engineering import (
    extract_features_and_target,
    validate_no_data_leakage,
    FORBIDDEN_FIELDS
)
from app.ml.train import train_recoverability_model
from app.ml.model_store import predict_recoverability, get_evaluation_metrics

client = TestClient(app)

def test_feature_extraction_and_leakage_validation():
    sample_df = pd.DataFrame([{
        "id": "txn_test_01",
        "amount": 2500.0,
        "retry_count": 0,
        "customer_historical_success_rate": 0.88,
        "latency_ms": 210,
        "risk_score": 0.05,
        "payment_method": "UPI",
        "gateway_id": "gtw_a",
        "issuer_id": "isr_hdfc",
        "failure_category": "TECHNICAL_TIMEOUT",
        "failure_code": "GATEWAY_TIMEOUT",
        "subscription_flag": False,
        "device_type": "MOBILE_ANDROID",
        "timestamp": "2026-09-01T10:00:00",
        "is_recoverable_ground_truth": True,
        # Post-action fields (should be ignored by extract_features_and_target)
        "status": "FAILED",
        "recovered_amount": 0.0
    }])

    X, y = extract_features_and_target(sample_df)
    assert len(X) == 1
    assert y.iloc[0] == 1
    assert "status" not in X.columns
    assert "recovered_amount" not in X.columns
    assert "is_recoverable_ground_truth" not in X.columns

    # Test that passing forbidden fields directly to validate_no_data_leakage raises ValueError
    leaked_df = pd.DataFrame([{"amount": 1000.0, "recovered_amount": 500.0}])
    with pytest.raises(ValueError, match="DATA LEAKAGE DETECTED"):
        validate_no_data_leakage(leaked_df)


def test_model_training_and_evaluation():
    report = train_recoverability_model(seed=42)

    assert "test_metrics" in report
    metrics = report["test_metrics"]

    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0
    assert 0.0 <= metrics["f1_score"] <= 1.0
    assert 0.0 <= metrics["roc_auc"] <= 1.0

    assert "baseline_comparison" in report
    assert "feature_importances" in report
    assert len(report["feature_importances"]) > 0

    # Verify model artifact files exist
    model_dir = Path(__file__).resolve().parent.parent / "app" / "ml" / "models"
    assert (model_dir / "recoverability_model.joblib").exists()
    assert (model_dir / "evaluation_results.json").exists()


def test_model_inference():
    sample_pre_action_input = {
        "amount": 3500.0,
        "retry_count": 0,
        "customer_historical_success_rate": 0.92,
        "latency_ms": 190,
        "risk_score": 0.04,
        "payment_method": "UPI",
        "gateway_id": "gtw_a",
        "issuer_id": "isr_hdfc",
        "failure_category": "TECHNICAL_TIMEOUT",
        "failure_code": "GATEWAY_TIMEOUT",
        "subscription_flag": "False",
        "device_type": "MOBILE_ANDROID"
    }

    result = predict_recoverability(sample_pre_action_input)
    assert "recoverability_probability" in result
    prob = result["recoverability_probability"]
    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0
    assert result["model_version"] == "1.0.0"


def test_evaluation_api_endpoint():
    response = client.get("/api/evaluation")
    assert response.status_code == 200
    data = response.json()
    assert "test_metrics" in data
    assert "baseline_comparison" in data
    assert "feature_importances" in data
