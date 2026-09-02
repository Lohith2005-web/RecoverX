from decimal import Decimal
from typing import Dict, Any, Tuple
from app.engine.constants import (
    RecoveryStrategy,
    DecisionConfidence,
    ConfidenceType,
    AutonomyAction,
    HIGH_CONFIDENCE_PROBABILITY_THRESHOLD,
    MEDIUM_CONFIDENCE_PROBABILITY_THRESHOLD,
    HIGH_RISK_SCORE_THRESHOLD
)

def determine_confidence_and_autonomy(
    recoverability_probability: float,
    selected_strategy: RecoveryStrategy,
    expected_economic_value: Decimal,
    transaction_data: Dict[str, Any]
) -> Tuple[DecisionConfidence, AutonomyAction, Dict[str, Any]]:
    """
    Evaluates policy thresholds to assign decision confidence and autonomy gate action.
    
    Returns (decision_confidence, autonomy_action, trace)
    """
    p_ml = float(recoverability_probability)
    ev = expected_economic_value
    failure_code = str(transaction_data.get("failure_code", "")).upper()
    risk_score = float(transaction_data.get("risk_score", 0.0))

    # 1. Determine Decision Confidence (Heuristic Policy)
    if p_ml >= HIGH_CONFIDENCE_PROBABILITY_THRESHOLD and ev > Decimal("0.00") and selected_strategy != RecoveryStrategy.DO_NOT_ACT:
        confidence = DecisionConfidence.HIGH
    elif p_ml >= MEDIUM_CONFIDENCE_PROBABILITY_THRESHOLD and ev > Decimal("0.00") and selected_strategy != RecoveryStrategy.DO_NOT_ACT:
        confidence = DecisionConfidence.MEDIUM
    else:
        confidence = DecisionConfidence.LOW

    # 2. Determine Autonomy Action Gate
    is_risk_reject = (failure_code == "RISK_REJECTED" or risk_score > HIGH_RISK_SCORE_THRESHOLD)

    if selected_strategy == RecoveryStrategy.DO_NOT_ACT or ev <= Decimal("0.00") or is_risk_reject:
        autonomy = AutonomyAction.DO_NOT_ACT
        gate_reason = "No actionable strategy has positive EV, or compliance risk blocked action."
    elif confidence == DecisionConfidence.HIGH:
        autonomy = AutonomyAction.AUTO_ACTION
        gate_reason = "High recoverability probability and positive expected economic value."
    elif confidence == DecisionConfidence.MEDIUM:
        autonomy = AutonomyAction.SIMULATE
        gate_reason = "Medium recoverability probability with positive expected economic value requires simulation or human approval."
    else:
        autonomy = AutonomyAction.DO_NOT_ACT
        gate_reason = "Low recoverability probability does not meet autonomy thresholds."

    trace = {
        "recoverability_probability": p_ml,
        "expected_economic_value": str(ev),
        "selected_strategy": selected_strategy.value,
        "is_risk_reject": is_risk_reject,
        "confidence": confidence.value,
        "confidence_type": ConfidenceType.HEURISTIC.value,
        "autonomy_action": autonomy.value,
        "gate_reason": gate_reason
    }

    return confidence, autonomy, trace
