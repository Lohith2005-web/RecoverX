import json
import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Transaction, RecoveryDecision, RecoveryExecution, AuditEvent, utc_now
from app.ml.model_store import predict_recoverability
from app.engine.strategy_selector import evaluate_recovery_decision
from app.engine.execution import simulate_execution_outcome, execute_recovery_decision
from app.engine.baseline_engine import evaluate_naive_baseline_and_recoverx

router = APIRouter()

def get_transaction_infer_data(transaction: Transaction) -> Dict[str, Any]:
    """Helper to extract feature payload for ML and engine from Transaction ORM model."""
    gateway_status = transaction.gateway.status if transaction.gateway else "HEALTHY"
    return {
        "id": transaction.id,
        "amount": transaction.amount,
        "retry_count": transaction.retry_count,
        "customer_historical_success_rate": transaction.customer_historical_success_rate,
        "latency_ms": transaction.latency_ms,
        "risk_score": transaction.risk_score,
        "payment_method": transaction.payment_method,
        "gateway_id": transaction.gateway_id,
        "issuer_id": transaction.issuer_id,
        "failure_category": transaction.failure_category,
        "failure_code": transaction.failure_code,
        "subscription_flag": str(transaction.subscription_flag),
        "device_type": transaction.device_type,
        "timestamp": transaction.timestamp.isoformat() if transaction.timestamp else None,
        "gateway_status": gateway_status
    }


@router.get("/recovery/opportunities")
def get_recovery_opportunities(
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Returns list of failed payment transactions that present potential recovery opportunities.
    """
    query = db.query(Transaction).filter(Transaction.status == "FAILED")
    total_count = query.count()
    txns = query.order_by(Transaction.timestamp.desc()).offset(offset).limit(limit).all()

    opportunities = []
    for txn in txns:
        infer_data = get_transaction_infer_data(txn)
        pred = predict_recoverability(infer_data)
        dec = evaluate_recovery_decision(pred["recoverability_probability"], txn.amount, infer_data)
        
        opportunities.append({
            "transaction_id": txn.id,
            "amount": txn.amount,
            "payment_method": txn.payment_method,
            "failure_code": txn.failure_code,
            "failure_category": txn.failure_category,
            "recoverability_probability": dec["recoverability_probability"],
            "recommended_strategy": dec["strategy"],
            "expected_economic_value": dec["expected_economic_value"],
            "decision_confidence": dec["decision_confidence"],
            "autonomy_action": dec["autonomy_action"],
            "timestamp": txn.timestamp.isoformat() if txn.timestamp else None
        })

    return {
        "total_opportunities": total_count,
        "limit": limit,
        "offset": offset,
        "opportunities": opportunities
    }


@router.get("/recovery/decision/{transaction_id}")
def get_recovery_decision(
    transaction_id: str = Path(..., description="ID of the failed transaction"),
    db: Session = Depends(get_db)
):
    """
    Computes or retrieves the Economic Recovery Decision for a single transaction.
    """
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found.")

    infer_data = get_transaction_infer_data(transaction)
    ml_pred = predict_recoverability(infer_data)
    decision_dict = evaluate_recovery_decision(ml_pred["recoverability_probability"], transaction.amount, infer_data)

    return {
        "transaction_id": transaction.id,
        "transaction_amount": transaction.amount,
        "failure_code": transaction.failure_code,
        "failure_category": transaction.failure_category,
        "gateway_status": infer_data["gateway_status"],
        "recoverability_model_prediction": ml_pred,
        "decision": decision_dict
    }


@router.post("/recovery/decision/{transaction_id}")
def generate_and_save_recovery_decision(
    transaction_id: str = Path(..., description="ID of the failed transaction"),
    db: Session = Depends(get_db)
):
    """
    Generates an economic decision, persists it to the database, and creates an audit record.
    """
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found.")

    infer_data = get_transaction_infer_data(transaction)
    ml_pred = predict_recoverability(infer_data)
    dec_dict = evaluate_recovery_decision(ml_pred["recoverability_probability"], transaction.amount, infer_data)

    dec_id = f"dec_{uuid.uuid4().hex[:10]}"
    decision = RecoveryDecision(
        id=dec_id,
        transaction_id=transaction.id,
        strategy=dec_dict["strategy"],
        recoverability_probability=dec_dict["recoverability_probability"],
        strategy_success_probability=dec_dict["strategy_success_probability"],
        expected_recovery=dec_dict["expected_recovery"],
        recovery_cost=dec_dict["recovery_cost"],
        customer_friction_cost=dec_dict["customer_friction_cost"],
        risk_penalty=dec_dict["risk_penalty"],
        expected_economic_value=dec_dict["expected_economic_value"],
        decision_confidence=dec_dict["decision_confidence"],
        confidence_type=dec_dict["confidence_type"],
        autonomy_action=dec_dict["autonomy_action"],
        explanation_json=json.dumps(dec_dict["explanation"]),
        created_at=utc_now()
    )
    db.add(decision)

    audit_event = AuditEvent(
        id=f"aud_{uuid.uuid4().hex[:10]}",
        transaction_id=transaction.id,
        decision_id=dec_id,
        event_type="DECISION_GENERATED",
        event_data=json.dumps(dec_dict),
        timestamp=utc_now()
    )
    db.add(audit_event)

    db.commit()
    db.refresh(decision)

    return {
        "status": "success",
        "decision_id": decision.id,
        "transaction_id": transaction.id,
        "decision": dec_dict
    }


@router.post("/recovery/simulate/{transaction_id}")
def simulate_recovery(
    transaction_id: str = Path(..., description="ID of the failed transaction"),
    seed: Optional[int] = Query(None, description="Optional seed for simulation reproducibility"),
    db: Session = Depends(get_db)
):
    """
    Simulates recovery execution for a transaction WITHOUT mutating financial or transaction database state.
    """
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found.")

    infer_data = get_transaction_infer_data(transaction)
    ml_pred = predict_recoverability(infer_data)
    dec_dict = evaluate_recovery_decision(ml_pred["recoverability_probability"], transaction.amount, infer_data)

    outcome = simulate_execution_outcome(dec_dict, infer_data, seed=seed)

    return {
        "transaction_id": transaction.id,
        "transaction_amount": transaction.amount,
        "decision": {
            "strategy": dec_dict["strategy"],
            "recoverability_probability": dec_dict["recoverability_probability"],
            "strategy_success_probability": dec_dict["strategy_success_probability"],
            "expected_economic_value": dec_dict["expected_economic_value"],
            "decision_confidence": dec_dict["decision_confidence"],
            "autonomy_action": dec_dict["autonomy_action"]
        },
        "simulated_outcome": outcome,
        "mutation_occurred": False,
        "is_simulated": True
    }


@router.post("/recovery/execute/{transaction_id}")
def execute_recovery(
    transaction_id: str = Path(..., description="ID of the failed transaction"),
    decision_id: Optional[str] = Query(None, description="Optional explicit decision ID"),
    seed: Optional[int] = Query(None, description="Optional seed for simulation reproducibility"),
    db: Session = Depends(get_db)
):
    """
    Executes simulated recovery action:
    - Validates transaction has not already been recovered.
    - Prevents duplicate execution.
    - Updates transaction status & recovered amount in database.
    - Records RecoveryExecution and AuditEvent.
    """
    try:
        res = execute_recovery_decision(db, transaction_id=transaction_id, decision_id=decision_id, seed=seed)
        return res
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/recovery/metrics")
def get_recovery_metrics(db: Session = Depends(get_db)):
    """
    Returns aggregate operational and financial metrics of RecoverX decision engine.
    """
    decisions = db.query(RecoveryDecision).all()
    executions = db.query(RecoveryExecution).all()

    total_decisions = len(decisions)
    total_executions = len(executions)

    strategy_counts: Dict[str, int] = {}
    autonomy_counts: Dict[str, int] = {}
    total_ev = 0.0

    for d in decisions:
        strategy_counts[d.strategy] = strategy_counts.get(d.strategy, 0) + 1
        autonomy_counts[d.autonomy_action] = autonomy_counts.get(d.autonomy_action, 0) + 1
        total_ev += d.expected_economic_value

    successful_executions = sum(1 for e in executions if e.simulated_success)
    total_recovered_amount = sum(e.recovered_amount for e in executions)
    total_net_recovered = sum(e.net_recovered_amount for e in executions)

    return {
        "total_decisions_generated": total_decisions,
        "total_executions_recorded": total_executions,
        "successful_executions": successful_executions,
        "execution_success_rate": round(successful_executions / max(1, total_executions), 4),
        "total_expected_economic_value": round(total_ev, 2),
        "total_recovered_amount": round(total_recovered_amount, 2),
        "total_net_recovered_amount": round(total_net_recovered, 2),
        "strategy_distribution": strategy_counts,
        "autonomy_action_distribution": autonomy_counts
    }


@router.get("/recovery/baseline")
def get_recovery_baseline_comparison(db: Session = Depends(get_db)):
    """
    Evaluates and returns comparison metrics between RecoverX Economic Engine and Naive Single-Retry Baseline
    on the current transaction population.
    """
    metrics = evaluate_naive_baseline_and_recoverx(db)
    return metrics
