from fastapi import APIRouter
from app.ml.model_store import get_evaluation_metrics, reload_model
from app.ml.train import train_recoverability_model

router = APIRouter()

@router.get("/evaluation")
def get_model_evaluation():
    """
    Returns authentic test-set evaluation metrics for the trained XGBoost model and baseline comparison.
    """
    metrics = get_evaluation_metrics()
    return metrics

@router.post("/evaluation/train")
def retrain_model():
    """
    Retrains the XGBoost recoverability model on current database dataset.
    """
    report = train_recoverability_model()
    reload_model()
    return {
        "status": "success",
        "message": "Model retrained and loaded into memory successfully.",
        "metrics": report["test_metrics"]
    }
