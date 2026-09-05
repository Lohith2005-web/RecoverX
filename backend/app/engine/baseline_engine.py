from decimal import Decimal
from typing import Dict, Any, List
import pandas as pd
from sqlalchemy.orm import Session, joinedload
from app.db.models import Transaction, Gateway
from app.ml.model_store import predict_recoverability
from app.engine.strategy_selector import evaluate_recovery_decision
from app.engine.economic_model import to_decimal

def evaluate_naive_baseline_and_recoverx(db: Session) -> Dict[str, Any]:
    """
    Evaluates RecoverX Economic Decision Engine against the Naive Single-Retry Baseline
    on the EXACT SAME dataset/population of failed transactions.
    
    Uses Decimal for monetary metrics.
    """
    failed_transactions = db.query(Transaction).filter(Transaction.status == "FAILED").all()

    if not failed_transactions:
        failed_transactions = db.query(Transaction).filter(Transaction.failure_code != "SUCCESS").all()




    total_failed = len(failed_transactions)

    if total_failed == 0:
        return {
            "dataset_summary": {"total_failed_transactions": 0, "evaluation_population_size": 0},
            "baseline_naive_retry": {
                "name": "Naive Single Retry Baseline",
                "evaluated_population_size": 0,
                "eligible_failed_transactions": 0,
                "attempted_recoveries": 0,
                "successful_recoveries": 0,
                "recovery_rate": 0.0,
                "gross_recovered_amount": 0.0,
                "recovery_cost": 0.0,
                "customer_friction_cost": 0.0,
                "risk_penalty": 0.0,
                "net_recovered_amount": 0.0,
                "expected_economic_value": 0.0
            },
            "recoverx_engine": {
                "name": "RecoverX Economic Decision Engine",
                "evaluated_population_size": 0,
                "eligible_failed_transactions": 0,
                "attempted_recoveries": 0,
                "successful_recoveries": 0,
                "recovery_rate": 0.0,
                "gross_recovered_amount": 0.0,
                "recovery_cost": 0.0,
                "customer_friction_cost": 0.0,
                "risk_penalty": 0.0,
                "net_recovered_amount": 0.0,
                "expected_economic_value": 0.0
            },
            "comparison": {
                "net_revenue_lift": 0.0,
                "actions_avoided": 0,
                "recovery_attempts_avoided": 0,
                "cost_reduction": 0.0,
                "summary": "No failed transactions found in evaluation population."
            }
        }

    # Batch prepare feature rows for fast ML inference
    infer_rows = []
    for txn in failed_transactions:
        infer_rows.append({
            "amount": float(txn.amount),
            "retry_count": txn.retry_count,
            "customer_historical_success_rate": txn.customer_historical_success_rate,
            "latency_ms": txn.latency_ms,
            "risk_score": txn.risk_score,
            "payment_method": txn.payment_method,
            "gateway_id": txn.gateway_id,
            "issuer_id": txn.issuer_id,
            "failure_category": txn.failure_category,
            "failure_code": txn.failure_code,
            "subscription_flag": str(txn.subscription_flag),
            "device_type": txn.device_type,
            "timestamp": txn.timestamp.isoformat() if txn.timestamp else "2026-09-01T12:00:00"
        })

    # Batch ML inference
    df_infer = pd.DataFrame(infer_rows)
    from app.ml.feature_engineering import NUMERICAL_FEATURES, CATEGORICAL_FEATURES
    from app.ml.model_store import get_model
    
    if "timestamp" in df_infer.columns:
        timestamps = pd.to_datetime(df_infer["timestamp"])
        df_infer["hour_of_day"] = timestamps.dt.hour
        df_infer["day_of_week"] = timestamps.dt.dayofweek
    else:
        df_infer["hour_of_day"] = 12
        df_infer["day_of_week"] = 0

    all_features = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
    X_infer = df_infer[all_features]
    pipeline = get_model()
    ml_probabilities = pipeline.predict_proba(X_infer)[:, 1]

    # Metrics accumulators (Decimal for monetary)
    b_eligible_count = 0
    b_attempted_count = 0
    b_successful_count = 0
    b_gross_recovered_dec = Decimal("0.00")
    b_recovery_cost_dec = Decimal("0.00")
    b_friction_cost_dec = Decimal("0.00")
    b_risk_penalty_dec = Decimal("0.00")

    rx_eligible_count = total_failed
    rx_attempted_count = 0
    rx_successful_count = 0
    rx_gross_recovered_dec = Decimal("0.00")
    rx_recovery_cost_dec = Decimal("0.00")
    rx_friction_cost_dec = Decimal("0.00")
    rx_risk_penalty_dec = Decimal("0.00")
    rx_expected_ev_dec = Decimal("0.00")

    for idx, txn in enumerate(failed_transactions):
        amount_dec = to_decimal(txn.amount)
        risk_score = float(txn.risk_score)
        is_risk_reject = (txn.failure_code == "RISK_REJECTED" or risk_score > 0.35)

        # ----------------------------------------------------
        # 1. NAIVE SINGLE RETRY BASELINE EVALUATION
        # ----------------------------------------------------
        b_eligible = (not is_risk_reject and txn.retry_count < 3)
        if b_eligible:
            b_eligible_count += 1
            b_attempted_count += 1

            rec_cost = Decimal("10.00")
            fric_cost = Decimal("2.00")
            risk_pen = to_decimal(risk_score * 50.0)

            b_recovery_cost_dec += rec_cost
            b_friction_cost_dec += fric_cost
            b_risk_penalty_dec += risk_pen

            if txn.is_recoverable_ground_truth:
                b_successful_count += 1
                b_gross_recovered_dec += amount_dec

        # ----------------------------------------------------
        # 2. RECOVERX DECISION ENGINE EVALUATION
        # ----------------------------------------------------
        p_ml = float(ml_probabilities[idx])
        gateway_status = txn.gateway.status if txn.gateway else "HEALTHY"
        infer_input = infer_rows[idx]

        dec = evaluate_recovery_decision(p_ml, txn.amount, {**infer_input, "gateway_status": gateway_status})

        strategy = dec["strategy"]
        if strategy != "DO_NOT_ACT":
            rx_attempted_count += 1
            
            rec_cost = to_decimal(dec["recovery_cost"])
            fric_cost = to_decimal(dec["customer_friction_cost"])
            risk_pen = to_decimal(dec["risk_penalty"])
            ev_dec = to_decimal(dec["expected_economic_value"])

            rx_recovery_cost_dec += rec_cost
            rx_friction_cost_dec += fric_cost
            rx_risk_penalty_dec += risk_pen
            rx_expected_ev_dec += ev_dec

            if txn.is_recoverable_ground_truth and dec["strategy_success_probability"] >= 0.35:
                rx_successful_count += 1
                rx_gross_recovered_dec += amount_dec

    b_net_recovered_dec = b_gross_recovered_dec - b_recovery_cost_dec - b_friction_cost_dec - b_risk_penalty_dec
    rx_net_recovered_dec = rx_gross_recovered_dec - rx_recovery_cost_dec - rx_friction_cost_dec - rx_risk_penalty_dec

    b_recovery_rate = round(b_successful_count / max(1, b_attempted_count), 4)
    rx_recovery_rate = round(rx_successful_count / max(1, rx_attempted_count), 4)

    actions_avoided = max(0, b_attempted_count - rx_attempted_count)

    return {
        "dataset_summary": {
            "total_failed_transactions": total_failed,
            "evaluation_population_size": total_failed
        },
        "baseline_naive_retry": {
            "name": "Naive Single Retry Baseline",
            "evaluated_population_size": total_failed,
            "eligible_failed_transactions": b_eligible_count,
            "attempted_recoveries": b_attempted_count,
            "successful_recoveries": b_successful_count,
            "recovery_rate": b_recovery_rate,
            "gross_recovered_amount": float(b_gross_recovered_dec),
            "recovery_cost": float(b_recovery_cost_dec),
            "customer_friction_cost": float(b_friction_cost_dec),
            "risk_penalty": float(b_risk_penalty_dec),
            "net_recovered_amount": float(b_net_recovered_dec),
            "expected_economic_value": float(b_net_recovered_dec)
        },
        "recoverx_engine": {
            "name": "RecoverX Economic Decision Engine",
            "evaluated_population_size": total_failed,
            "eligible_failed_transactions": rx_eligible_count,
            "attempted_recoveries": rx_attempted_count,
            "successful_recoveries": rx_successful_count,
            "recovery_rate": rx_recovery_rate,
            "gross_recovered_amount": float(rx_gross_recovered_dec),
            "recovery_cost": float(rx_recovery_cost_dec),
            "customer_friction_cost": float(rx_friction_cost_dec),
            "risk_penalty": float(rx_risk_penalty_dec),
            "net_recovered_amount": float(rx_net_recovered_dec),
            "expected_economic_value": float(rx_expected_ev_dec)
        },
        "comparison": {
            "net_revenue_lift": float(rx_net_recovered_dec - b_net_recovered_dec),
            "actions_avoided": actions_avoided,
            "recovery_attempts_avoided": actions_avoided,
            "percentage_fewer_recovery_attempts": round((actions_avoided / max(1, b_attempted_count)) * 100, 1),
            "cost_reduction": float((b_recovery_cost_dec + b_friction_cost_dec) - (rx_recovery_cost_dec + rx_friction_cost_dec)),
            "summary": f"RecoverX made {actions_avoided} fewer recovery attempts ({round((actions_avoided / max(1, b_attempted_count)) * 100, 1)}% reduction) while achieving net recovered revenue of ₹{float(rx_net_recovered_dec):.2f}."
        }
    }
