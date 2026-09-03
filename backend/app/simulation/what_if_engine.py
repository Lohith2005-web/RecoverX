import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import Transaction, Gateway
from app.engine.economic_model import to_decimal
from app.engine.strategy_selector import evaluate_recovery_decision
from app.engine.baseline_engine import evaluate_naive_baseline_and_recoverx
from app.ml.model_store import predict_recoverability
from app.simulation.constants import ScenarioType

def run_what_if_simulation(
    db: Session,
    scenario_name: str = "Counterfactual Simulation",
    scenario_type: ScenarioType = ScenarioType.CURRENT_CONDITIONS,
    gateway_status_overrides: Optional[Dict[str, str]] = None,
    recoverability_threshold: float = 0.70,
    strategy_overrides: Optional[Dict[str, str]] = None,
    include_baseline: bool = True,
    observation_hours: int = 72
) -> Dict[str, Any]:
    """
    Pure counterfactual what-if simulation engine.
    Does NOT mutate transactions, incidents, recovery executions, or baseline data.
    Uses Decimal precision for all financial calculations.
    """
    gateway_status_overrides = gateway_status_overrides or {}
    strategy_overrides = strategy_overrides or {}

    latest_ts = db.query(func.max(Transaction.timestamp)).scalar()
    if not latest_ts:
        return {
            "scenario_name": scenario_name,
            "scenario_type": scenario_type.value if isinstance(scenario_type, ScenarioType) else str(scenario_type),
            "error": "No transaction data available"
        }

    window_start = latest_ts - datetime.timedelta(hours=observation_hours)
    failed_txns = db.query(Transaction).filter(
        Transaction.timestamp >= window_start,
        Transaction.status == "FAILED"
    ).all()

    # Load Gateway mapping
    gateways = db.query(Gateway).all()
    gtw_map = {g.id: g for g in gateways}

    transactions_considered = len(failed_txns)
    eligible_count = 0
    
    predicted_recoverable_dec = Decimal("0.00")
    gross_expected_recovery_dec = Decimal("0.00")
    expected_cost_dec = Decimal("0.00")
    expected_friction_dec = Decimal("0.00")
    expected_risk_dec = Decimal("0.00")
    
    expected_attempts = 0
    expected_successes_dec = Decimal("0.00")

    # Counterfactual evaluation per failed transaction
    for t in failed_txns:
        amount_dec = to_decimal(t.amount)
        gtw_obj = gtw_map.get(t.gateway_id)
        gtw_code = gtw_obj.code if gtw_obj else "unknown"

        # Apply counterfactual gateway health override if present
        effective_gtw_status = gateway_status_overrides.get(gtw_code, gtw_obj.status if gtw_obj else "HEALTHY")

        infer_input = {
            "amount": float(t.amount),
            "retry_count": t.retry_count,
            "customer_historical_success_rate": t.customer_historical_success_rate,
            "latency_ms": t.latency_ms,
            "risk_score": t.risk_score,
            "payment_method": t.payment_method,
            "gateway_id": t.gateway_id,
            "issuer_id": t.issuer_id,
            "failure_category": t.failure_category,
            "failure_code": t.failure_code,
            "subscription_flag": str(t.subscription_flag),
            "device_type": t.device_type,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "gateway_status": effective_gtw_status
        }

        # Predict ML recoverability P_ml
        ml_pred = predict_recoverability(infer_input)
        p_ml = ml_pred["recoverability_probability"]
        p_ml_dec = Decimal(str(round(p_ml, 4)))

        # Track expected recoverable revenue (amount * P_ml)
        predicted_recoverable_dec += (amount_dec * p_ml_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Evaluate candidate strategies using Phase 3 engine
        decision = evaluate_recovery_decision(p_ml, float(t.amount), infer_input)
        selected_strategy = decision["strategy"]

        # Check if strategy override is defined for this failure code
        if t.failure_code in strategy_overrides:
            selected_strategy = strategy_overrides[t.failure_code]

        # Actionability condition: Strategy != DO_NOT_ACT and P_ml >= recoverability_threshold
        if selected_strategy != "DO_NOT_ACT" and p_ml >= recoverability_threshold:
            eligible_count += 1
            expected_attempts += 1
            
            p_success_dec = Decimal(str(round(decision["strategy_success_probability"], 4)))
            expected_successes_dec += p_success_dec

            exp_rec = (amount_dec * p_success_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            gross_expected_recovery_dec += exp_rec
            expected_cost_dec += to_decimal(decision["recovery_cost"])
            expected_friction_dec += to_decimal(decision["customer_friction_cost"])
            expected_risk_dec += to_decimal(decision["risk_penalty"])

    expected_net_recovery_dec = (
        gross_expected_recovery_dec - expected_cost_dec - expected_friction_dec - expected_risk_dec
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Derived metrics
    attempts_divisor = max(1, expected_attempts)
    success_rate = round(float(expected_successes_dec) / attempts_divisor, 4) if expected_attempts > 0 else 0.0
    rev_per_action = (expected_net_recovery_dec / Decimal(str(attempts_divisor))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    succ_divisor = max(Decimal("0.0001"), expected_successes_dec)
    cost_per_success = (expected_cost_dec / succ_divisor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if expected_successes_dec > Decimal("0.00") else Decimal("0.00")
    avoided_attempts = transactions_considered - expected_attempts

    # Baseline comparison metrics
    baseline_metrics = {}
    inc_revenue_vs_base = Decimal("0.00")
    inc_net_vs_base = Decimal("0.00")

    if include_baseline:
        base_eval = evaluate_naive_baseline_and_recoverx(db)
        base_dict = base_eval.get("baseline_naive_retry", {})
        base_gross = to_decimal(base_dict.get("gross_recovered_amount", 0.0))
        base_net = to_decimal(base_dict.get("net_recovered_amount", 0.0))

        inc_revenue_vs_base = gross_expected_recovery_dec - base_gross
        inc_net_vs_base = expected_net_recovery_dec - base_net

        baseline_metrics = {
            "naive_baseline_gross_recovery": float(base_gross),
            "naive_baseline_net_recovery": float(base_net),
            "naive_baseline_attempts": base_dict.get("eligible_failed_transactions", 0)
        }


    return {
        "scenario_name": scenario_name,
        "scenario_type": scenario_type.value if isinstance(scenario_type, ScenarioType) else str(scenario_type),
        "parameters": {
            "gateway_status_overrides": gateway_status_overrides,
            "recoverability_threshold": recoverability_threshold,
            "strategy_overrides": strategy_overrides
        },
        "metrics": {
            "transactions_considered": transactions_considered,
            "eligible_transactions": eligible_count,
            "predicted_recoverable_amount": float(predicted_recoverable_dec),
            "gross_expected_recovery": float(gross_expected_recovery_dec),
            "expected_recovery_cost": float(expected_cost_dec),
            "expected_friction": float(expected_friction_dec),
            "expected_risk_penalty": float(expected_risk_dec),
            "expected_net_recovery": float(expected_net_recovery_dec),
            "expected_attempts": expected_attempts,
            "expected_successes": round(float(expected_successes_dec), 2),
            "expected_success_rate": success_rate,
            "revenue_per_action": float(rev_per_action),
            "cost_per_successful_recovery": float(cost_per_success),
            "avoided_attempts": avoided_attempts,
            "incremental_revenue_vs_baseline": float(inc_revenue_vs_base),
            "incremental_net_recovery_vs_baseline": float(inc_net_vs_base)
        },
        "baseline_comparison": baseline_metrics
    }
