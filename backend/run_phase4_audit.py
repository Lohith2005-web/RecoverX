import sys
import json
import os
from pathlib import Path

# Ensure UTF-8 output encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.session import engine, Base, SessionLocal
from app.db.models import Transaction, Gateway
from app.simulator.generator import seed_database
from app.simulator.scenario_engine import inject_gateway_degradation
from app.incidents.incident_manager import process_and_group_incidents
from app.engine.constants import RecoveryStrategy
from app.engine.economic_model import calculate_strategy_probability, calculate_economic_value
from app.engine.strategy_selector import evaluate_recovery_decision
from app.ml.model_store import predict_recoverability

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    print("1. Initializing database with seed 42...")
    seed_database(db, num_transactions=5000, seed=42)

    print("\n2. Injecting Gateway B Degradation Scenario...")
    scen_res = inject_gateway_degradation(db, gateway_code="gateway_b")
    print(f"Scenario injection result: {scen_res}")

    print("\n3. Triggering Phase 4 Incident Detection Engine...")
    incidents = process_and_group_incidents(db, observation_hours=72)
    print(f"Detected Incidents Count: {len(incidents)}")
    if incidents:
        print(f"Primary Incident Title: {incidents[0]['title']}")
        print(f"Root Cause: {incidents[0]['root_cause']}")
        print(f"Confidence: {incidents[0]['confidence']} ({incidents[0]['confidence_type']})")

    # Fetch a failed transaction on degraded Gateway B
    gtw_b = db.query(Gateway).filter(Gateway.code == "gateway_b").first()
    print(f"\nGateway B Status in DB: {gtw_b.status}")

    sample_txn = db.query(Transaction).filter(
        Transaction.gateway_id == gtw_b.id,
        Transaction.status == "FAILED",
        Transaction.scenario_tag == "GATEWAY_B_DEGRADATION",
        Transaction.customer_historical_success_rate >= 0.85
    ).first()

    if not sample_txn:
        sample_txn = db.query(Transaction).filter(Transaction.gateway_id == gtw_b.id, Transaction.status == "FAILED").first()

    print(f"\nSelected Sample Transaction ID: {sample_txn.id}")
    print(f"Amount: ₹{sample_txn.amount}")
    print(f"Failure Code: {sample_txn.failure_code}")
    print(f"Failure Category: {sample_txn.failure_category}")
    print(f"Customer Hist Success Rate: {sample_txn.customer_historical_success_rate}")

    infer_input = {
        "amount": sample_txn.amount,
        "retry_count": sample_txn.retry_count,
        "customer_historical_success_rate": sample_txn.customer_historical_success_rate,
        "latency_ms": sample_txn.latency_ms,
        "risk_score": sample_txn.risk_score,
        "payment_method": sample_txn.payment_method,
        "gateway_id": sample_txn.gateway_id,
        "issuer_id": sample_txn.issuer_id,
        "failure_category": sample_txn.failure_category,
        "failure_code": sample_txn.failure_code,
        "subscription_flag": str(sample_txn.subscription_flag),
        "device_type": sample_txn.device_type,
        "timestamp": sample_txn.timestamp.isoformat() if sample_txn.timestamp else None,
        "gateway_status": gtw_b.status
    }

    ml_pred = predict_recoverability(infer_input)
    p_ml = ml_pred["recoverability_probability"]
    print(f"\nPhase 2 ML Recoverability Probability (P_ml): {p_ml}")

    print("\n========================================================")
    print("4. EVALUATING ALL CANDIDATE STRATEGIES (Standard +0.25 Adjustment)")
    print("========================================================")

    all_strategies = [
        RecoveryStrategy.SMART_RETRY,
        RecoveryStrategy.GATEWAY_REROUTE,
        RecoveryStrategy.PAYMENT_METHOD_RECOVERY,
        RecoveryStrategy.CUSTOMER_RECOVERY,
        RecoveryStrategy.DO_NOT_ACT
    ]

    strategy_evals = []
    for st in all_strategies:
        prob, prob_trace = calculate_strategy_probability(st, p_ml, infer_input)
        econ = calculate_economic_value(st, prob, sample_txn.amount, infer_input)
        raw_p = prob_trace.get("raw_prob", prob)
        
        eval_dict = {
            "strategy": st.value,
            "raw_prob": raw_p,
            "final_bounded_prob": prob,
            "expected_recovery": float(econ["expected_recovery"]),
            "recovery_cost": float(econ["recovery_cost"]),
            "friction_cost": float(econ["customer_friction_cost"]),
            "risk_penalty": float(econ["risk_penalty"]),
            "expected_economic_value": float(econ["expected_economic_value"])
        }
        strategy_evals.append(eval_dict)
        print(f"Strategy: {st.value:<25} | P_success: {prob:.4f} (Raw: {raw_p:.4f}) | EV: ₹{econ['expected_economic_value']:>10.2f}")

    winning_dec = evaluate_recovery_decision(p_ml, sample_txn.amount, infer_input)
    print(f"\n---> WINNING STRATEGY (Standard +0.25): {winning_dec['strategy']} with EV = ₹{winning_dec['expected_economic_value']:.2f}")

    print("\n========================================================")
    print("5. ROBUSTNESS CHECK: GATEWAY REROUTE ADJUSTMENT REDUCED TO +0.10")
    print("========================================================")

    strategy_evals_robust = []
    for st in all_strategies:
        if st == RecoveryStrategy.GATEWAY_REROUTE:
            # Manually substitute +0.10 delta instead of +0.25
            raw_p = p_ml + 0.10
            prob = round(max(0.01, min(0.99, raw_p)), 4)
        else:
            prob, prob_trace = calculate_strategy_probability(st, p_ml, infer_input)

        econ = calculate_economic_value(st, prob, sample_txn.amount, infer_input)
        eval_dict = {
            "strategy": st.value,
            "final_bounded_prob": prob,
            "expected_economic_value": float(econ["expected_economic_value"])
        }
        strategy_evals_robust.append(eval_dict)
        print(f"Strategy: {st.value:<25} | P_success: {prob:.4f} | EV: ₹{econ['expected_economic_value']:>10.2f}")

    # Determine robustness winner
    robust_winner = max(strategy_evals_robust, key=lambda x: x["expected_economic_value"])
    print(f"\n---> WINNING STRATEGY (+0.10 Robustness Check): {robust_winner['strategy']} with EV = ₹{robust_winner['expected_economic_value']:.2f}")

finally:
    db.close()
