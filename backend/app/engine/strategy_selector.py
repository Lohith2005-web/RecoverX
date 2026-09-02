from decimal import Decimal
from typing import Dict, Any, List
from app.engine.constants import (
    RecoveryStrategy,
    DecisionConfidence,
    ConfidenceType,
    AutonomyAction
)
from app.engine.economic_model import calculate_strategy_probability, calculate_economic_value
from app.engine.confidence_gate import determine_confidence_and_autonomy

ACTIONABLE_STRATEGIES = [
    RecoveryStrategy.SMART_RETRY,
    RecoveryStrategy.GATEWAY_REROUTE,
    RecoveryStrategy.PAYMENT_METHOD_RECOVERY,
    RecoveryStrategy.CUSTOMER_RECOVERY,
]

def make_json_serializable(obj: Any) -> Any:
    """Recursively converts Decimals and custom types to native JSON types."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(v) for v in obj]
    return obj

def evaluate_recovery_decision(
    recoverability_probability: float,
    transaction_amount: Any,
    transaction_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluates actionable recovery strategies against expected economic value and policy gates.
    
    Returns complete structured decision object including machine-readable decision_trace.
    """
    candidate_evaluations = []
    viable_candidates = []

    failure_code = str(transaction_data.get("failure_code", "")).upper()
    failure_category = str(transaction_data.get("failure_category", "")).upper()
    gateway_status = str(transaction_data.get("gateway_status", "HEALTHY")).upper()
    risk_score = float(transaction_data.get("risk_score", 0.0))
    p_ml = float(recoverability_probability)

    # Evaluate each actionable strategy
    for strategy in ACTIONABLE_STRATEGIES:
        prob, prob_trace = calculate_strategy_probability(strategy, recoverability_probability, transaction_data)
        econ = calculate_economic_value(strategy, prob, transaction_amount, transaction_data)
        
        eval_item = {
            "strategy": strategy.value,
            "strategy_success_probability": prob,
            "probability_trace": prob_trace,
            "transaction_amount": float(econ["transaction_amount"]),
            "expected_recovery": float(econ["expected_recovery"]),
            "recovery_cost": float(econ["recovery_cost"]),
            "customer_friction_cost": float(econ["customer_friction_cost"]),
            "risk_penalty": float(econ["risk_penalty"]),
            "expected_economic_value": float(econ["expected_economic_value"])
        }
        candidate_evaluations.append(eval_item)

        # Viable if expected economic value > 0, ML prob >= 0.70, and no strict compliance block
        if econ["expected_economic_value"] > Decimal("0.00") and p_ml >= 0.70 and failure_code != "RISK_REJECTED" and risk_score <= 0.35:
            viable_candidates.append((econ["expected_economic_value"], prob, strategy, econ, eval_item))

    # Decision selection policy
    reason_codes = []
    if viable_candidates:
        # Sort by highest expected economic value, then by success probability
        viable_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best_ev, best_prob, candidate_winning_strategy, winning_econ, winning_eval = viable_candidates[0]
        
        if candidate_winning_strategy == RecoveryStrategy.GATEWAY_REROUTE:
            reason_codes.append("CURRENT_GATEWAY_DEGRADED" if gateway_status != "HEALTHY" else "HIGH_RECOVERABILITY")
            reason_codes.append("GATEWAY_REROUTE_OPTIMAL")
            summary = f"Gateway reroute selected as current gateway is {gateway_status.lower()} and offers maximum expected net economic value."
        elif candidate_winning_strategy == RecoveryStrategy.SMART_RETRY:
            reason_codes.append("TRANSIENT_TECHNICAL_FAILURE" if failure_category == "TECHNICAL_TIMEOUT" else "HIGH_RECOVERABILITY")
            reason_codes.append("SMART_RETRY_OPTIMAL")
            summary = "Smart retry selected for transient technical failure with low friction cost."
        elif candidate_winning_strategy == RecoveryStrategy.PAYMENT_METHOD_RECOVERY:
            reason_codes.append("PAYMENT_METHOD_ISSUE")
            reason_codes.append("PAYMENT_RECOVERY_OPTIMAL")
            summary = "Payment method recovery selected for payment decline or fund availability issue."
        elif candidate_winning_strategy == RecoveryStrategy.CUSTOMER_RECOVERY:
            reason_codes.append("CUSTOMER_ACTION_REQUIRED")
            reason_codes.append("CUSTOMER_RECOVERY_OPTIMAL")
            summary = "Customer recovery selected as user intervention/re-authentication is required."
        else:
            reason_codes.append("POSITIVE_EV")
            summary = f"{candidate_winning_strategy.value} selected for positive expected economic value."
            
        reason_codes.append("POSITIVE_EXPECTED_VALUE")
        economic_reason = f"Expected recovery of ₹{winning_econ['expected_recovery']:.2f} exceeds total estimated costs of ₹{(winning_econ['recovery_cost'] + winning_econ['customer_friction_cost'] + winning_econ['risk_penalty']):.2f} by net EV ₹{best_ev:.2f}."
    else:
        candidate_winning_strategy = RecoveryStrategy.DO_NOT_ACT
        winning_econ = calculate_economic_value(candidate_winning_strategy, 0.0, transaction_amount, transaction_data)
        best_ev = winning_econ["expected_economic_value"]

        if failure_code == "RISK_REJECTED" or risk_score > 0.35:
            reason_codes.append("RISK_COMPLIANCE_REJECTED")
            summary = "DO_NOT_ACT selected due to high compliance risk score or risk rejection flag."
            economic_reason = "Risk penalty exceeds expected recovery value."
        elif p_ml < 0.70:
            reason_codes.append("LOW_RECOVERABILITY_PROBABILITY")
            summary = "DO_NOT_ACT selected because raw ML recoverability probability is below confidence threshold (< 0.70)."
            economic_reason = "Low recoverability probability yields low or non-positive expected economic value."
        else:
            reason_codes.append("NEGATIVE_OR_ZERO_EV")
            summary = "DO_NOT_ACT selected as no actionable recovery strategy produced positive expected economic value."
            economic_reason = "Estimated recovery costs and customer friction exceed expected gross recovery."

    # Determine confidence and autonomy action gate
    confidence, autonomy, conf_trace = determine_confidence_and_autonomy(
        recoverability_probability,
        candidate_winning_strategy,
        best_ev,
        transaction_data
    )

    if autonomy == AutonomyAction.DO_NOT_ACT:
        winning_strategy = RecoveryStrategy.DO_NOT_ACT
    else:
        winning_strategy = candidate_winning_strategy

    decision_trace = {
        "candidate_evaluations": candidate_evaluations,
        "viable_candidates_count": len(viable_candidates),
        "winning_strategy": winning_strategy.value,
        "winning_expected_economic_value": str(best_ev),
        "confidence_gate_trace": conf_trace
    }

    result = {
        "strategy": winning_strategy.value,
        "recoverability_probability": round(float(recoverability_probability), 4),
        "strategy_success_probability": float(winning_econ["strategy_success_probability"]),
        "expected_recovery": float(winning_econ["expected_recovery"]),
        "recovery_cost": float(winning_econ["recovery_cost"]),
        "customer_friction_cost": float(winning_econ["customer_friction_cost"]),
        "risk_penalty": float(winning_econ["risk_penalty"]),
        "expected_economic_value": float(winning_econ["expected_economic_value"]),
        "decision_confidence": confidence.value,
        "confidence_type": ConfidenceType.HEURISTIC.value,
        "autonomy_action": autonomy.value,
        "explanation": {
            "strategy": winning_strategy.value,
            "reason_codes": reason_codes,
            "summary": summary,
            "economic_reason": economic_reason,
            "confidence": confidence.value,
            "confidence_type": ConfidenceType.HEURISTIC.value
        },
        "decision_trace": decision_trace
    }

    return make_json_serializable(result)
