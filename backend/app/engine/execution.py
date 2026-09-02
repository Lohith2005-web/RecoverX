import json
import random
import uuid
import datetime
from decimal import Decimal
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.db.models import Transaction, RecoveryDecision, RecoveryExecution, AuditEvent, utc_now
from app.engine.economic_model import to_decimal

def simulate_execution_outcome(
    decision_data: Dict[str, Any],
    transaction_data: Dict[str, Any],
    seed: int = None
) -> Dict[str, Any]:
    """
    Pure simulation helper: Computes simulated outcome WITHOUT mutating DB state.
    Used by /simulate endpoint and execute workflow.
    """
    prob = float(decision_data.get("strategy_success_probability", 0.0))
    amount_dec = to_decimal(transaction_data.get("amount", 0.0))
    rec_cost_dec = to_decimal(decision_data.get("recovery_cost", 0.0))
    fric_cost_dec = to_decimal(decision_data.get("customer_friction_cost", 0.0))
    risk_pen_dec = to_decimal(decision_data.get("risk_penalty", 0.0))

    strategy = decision_data.get("strategy", "DO_NOT_ACT")

    if strategy == "DO_NOT_ACT":
        simulated_success = False
        recovered_amount_dec = Decimal("0.00")
    else:
        if seed is not None:
            rng = random.Random(seed)
            simulated_success = rng.random() < prob
        else:
            # Deterministic seed derived from transaction ID hash if no explicit seed passed
            txn_id = str(transaction_data.get("id", "txn"))
            seed_val = hash(txn_id) & 0xffffffff
            rng = random.Random(seed_val)
            simulated_success = rng.random() < prob

        recovered_amount_dec = amount_dec if simulated_success else Decimal("0.00")

    net_recovered_dec = recovered_amount_dec - rec_cost_dec - fric_cost_dec - risk_pen_dec

    return {
        "strategy": strategy,
        "simulated_success": simulated_success,
        "recovered_amount": float(recovered_amount_dec),
        "recovery_cost": float(rec_cost_dec),
        "friction_cost": float(fric_cost_dec),
        "risk_penalty": float(risk_pen_dec),
        "net_recovered_amount": float(net_recovered_dec),
        "is_simulated": True
    }

def execute_recovery_decision(
    db: Session,
    transaction_id: str,
    decision_id: str = None,
    seed: int = None
) -> Dict[str, Any]:
    """
    Executes a recovery decision for a transaction:
    - Validates transaction has not already been recovered.
    - Prevents duplicate execution.
    - Simulates recovery execution.
    - Updates transaction status & recovered amount in DB.
    - Saves RecoveryExecution & AuditEvent records.
    """
    # 1. Fetch transaction
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise ValueError(f"Transaction '{transaction_id}' not found.")

    if transaction.status == "RECOVERED":
        raise ValueError(f"Transaction '{transaction_id}' has already been recovered.")

    # 2. Fetch or generate decision
    if decision_id:
        decision = db.query(RecoveryDecision).filter(RecoveryDecision.id == decision_id).first()
        if not decision:
            raise ValueError(f"Recovery decision '{decision_id}' not found.")
    else:
        decision = db.query(RecoveryDecision).filter(RecoveryDecision.transaction_id == transaction_id).order_by(RecoveryDecision.created_at.desc()).first()
        if not decision:
            # Generate decision on the fly if missing
            from app.ml.model_store import predict_recoverability
            from app.engine.strategy_selector import evaluate_recovery_decision
            
            infer_data = {
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
                "timestamp": transaction.timestamp.isoformat() if transaction.timestamp else None
            }
            pred = predict_recoverability(infer_data)
            dec_dict = evaluate_recovery_decision(
                pred["recoverability_probability"],
                transaction.amount,
                {**infer_data, "gateway_status": transaction.gateway.status if transaction.gateway else "HEALTHY"}
            )
            decision = RecoveryDecision(
                id=f"dec_{uuid.uuid4().hex[:10]}",
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
                explanation_json=json.dumps(dec_dict["explanation"])
            )
            db.add(decision)
            db.commit()
            db.refresh(decision)

    # 3. Prevent duplicate execution
    existing_exec = db.query(RecoveryExecution).filter(RecoveryExecution.decision_id == decision.id).first()
    if existing_exec:
        raise ValueError(f"Duplicate execution prevented: Decision '{decision.id}' has already been executed.")

    # 4. Simulate outcome
    decision_dict = {
        "strategy": decision.strategy,
        "strategy_success_probability": decision.strategy_success_probability,
        "recovery_cost": decision.recovery_cost,
        "customer_friction_cost": decision.customer_friction_cost,
        "risk_penalty": decision.risk_penalty,
    }
    txn_dict = {
        "id": transaction.id,
        "amount": transaction.amount
    }
    outcome = simulate_execution_outcome(decision_dict, txn_dict, seed=seed)

    # 5. Mutate DB state on /execute
    exec_id = f"exec_{uuid.uuid4().hex[:10]}"
    execution = RecoveryExecution(
        id=exec_id,
        decision_id=decision.id,
        transaction_id=transaction.id,
        status="EXECUTED",
        simulated_success=outcome["simulated_success"],
        recovered_amount=outcome["recovered_amount"],
        recovery_cost=outcome["recovery_cost"],
        friction_cost=outcome["friction_cost"],
        risk_penalty=outcome["risk_penalty"],
        net_recovered_amount=outcome["net_recovered_amount"],
        executed_at=utc_now()
    )
    db.add(execution)

    if outcome["simulated_success"]:
        transaction.status = "RECOVERED"
        transaction.recovered_amount = outcome["recovered_amount"]

    # 6. Add Audit Event
    audit_id = f"aud_{uuid.uuid4().hex[:10]}"
    audit_event = AuditEvent(
        id=audit_id,
        transaction_id=transaction.id,
        decision_id=decision.id,
        event_type="RECOVERY_EXECUTED",
        event_data=json.dumps(outcome),
        timestamp=utc_now()
    )
    db.add(audit_event)

    db.commit()
    db.refresh(execution)

    return {
        "execution_id": execution.id,
        "decision_id": decision.id,
        "transaction_id": transaction.id,
        "strategy": execution.decision.strategy if execution.decision else decision.strategy,
        "simulated_success": execution.simulated_success,
        "recovered_amount": execution.recovered_amount,
        "recovery_cost": execution.recovery_cost,
        "friction_cost": execution.friction_cost,
        "risk_penalty": execution.risk_penalty,
        "net_recovered_amount": execution.net_recovered_amount,
        "executed_at": execution.executed_at.isoformat(),
        "is_simulated": True
    }
