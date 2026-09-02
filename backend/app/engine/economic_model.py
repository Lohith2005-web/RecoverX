from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Tuple
from app.engine.constants import (
    RecoveryStrategy,
    STRATEGY_BASE_COSTS,
    STRATEGY_FRICTION_COSTS,
    HIGH_RISK_SCORE_THRESHOLD
)

def to_decimal(val: Any) -> Decimal:
    """Helper to cleanly convert float/int/str to Decimal with 2 decimal places."""
    if isinstance(val, Decimal):
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal(str(round(float(val), 2))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def calculate_strategy_probability(
    strategy: RecoveryStrategy,
    recoverability_probability: float,
    transaction_data: Dict[str, Any]
) -> Tuple[float, Dict[str, Any]]:
    """
    Computes a transparent, bounded, deterministic strategy-specific probability
    P(strategy_success) using Phase 2 recoverability probability + evidence adjustments.
    
    Returns (strategy_probability, adjustment_trace)
    """
    if strategy == RecoveryStrategy.DO_NOT_ACT:
        return 0.0, {"base_ml_prob": recoverability_probability, "adjustments": [], "final_prob": 0.0}

    p_base = float(recoverability_probability)
    adjustments = []
    
    failure_category = str(transaction_data.get("failure_category", "")).upper()
    failure_code = str(transaction_data.get("failure_code", "")).upper()
    gateway_status = str(transaction_data.get("gateway_status", "HEALTHY")).upper()
    retry_count = int(transaction_data.get("retry_count", 0))
    customer_hist_rate = float(transaction_data.get("customer_historical_success_rate", 0.85))
    subscription_flag = bool(transaction_data.get("subscription_flag", False))
    risk_score = float(transaction_data.get("risk_score", 0.0))

    delta = 0.0

    if strategy == RecoveryStrategy.SMART_RETRY:
        # Technical/transient failures benefit from smart retry
        if failure_category == "TECHNICAL_TIMEOUT" or failure_code in ["GATEWAY_TIMEOUT", "NETWORK_ERROR"]:
            adj = 0.05
            delta += adj
            adjustments.append({"factor": "TRANSIENT_TECHNICAL_FAILURE", "delta": adj})

        # Penalty for existing retries
        if retry_count > 0:
            adj = -0.15 * retry_count
            delta += adj
            adjustments.append({"factor": f"PREVIOUS_RETRIES_{retry_count}", "delta": round(adj, 4)})

        # Penalty if current gateway is degraded
        if gateway_status != "HEALTHY":
            adj = -0.25
            delta += adj
            adjustments.append({"factor": "GATEWAY_DEGRADED", "delta": adj})

        # Penalty for non-transient failures
        if failure_code in ["RISK_REJECTED", "CARD_EXPIRED", "INSUFFICIENT_FUNDS"]:
            adj = -0.40
            delta += adj
            adjustments.append({"factor": "NON_TRANSIENT_FAILURE", "delta": adj})

    elif strategy == RecoveryStrategy.GATEWAY_REROUTE:
        # Highly effective when current gateway is degraded
        if gateway_status != "HEALTHY":
            adj = 0.25
            delta += adj
            adjustments.append({"factor": "CURRENT_GATEWAY_DEGRADED", "delta": adj})
        else:
            adj = -0.10
            delta += adj
            adjustments.append({"factor": "GATEWAY_HEALTHY_REROUTE_OVERHEAD", "delta": adj})

        # User/compliance failures cannot be solved by gateway reroute
        if failure_code in ["INSUFFICIENT_FUNDS", "RISK_REJECTED", "CARD_EXPIRED"]:
            adj = -0.50
            delta += adj
            adjustments.append({"factor": "UNHANDLED_FAILURE_CODE_FOR_REROUTE", "delta": adj})

    elif strategy == RecoveryStrategy.PAYMENT_METHOD_RECOVERY:
        # Card / insufficient funds issues
        if failure_code in ["INSUFFICIENT_FUNDS", "CARD_EXPIRED", "CARD_DECLINED"]:
            adj = 0.15
            delta += adj
            adjustments.append({"factor": "PAYMENT_METHOD_FAILURE_MATCH", "delta": adj})

        if customer_hist_rate >= 0.85:
            adj = 0.10
            delta += adj
            adjustments.append({"factor": "HIGH_CUSTOMER_HISTORICAL_SUCCESS", "delta": adj})

        if failure_category == "TECHNICAL_TIMEOUT" or failure_code in ["GATEWAY_TIMEOUT", "NETWORK_ERROR"]:
            adj = -0.20
            delta += adj
            adjustments.append({"factor": "PURE_TECHNICAL_TIMEOUT", "delta": adj})

    elif strategy == RecoveryStrategy.CUSTOMER_RECOVERY:
        # Customer action required (OTP, PIN, authentication)
        if failure_code in ["AUTHENTICATION_FAILED", "OTP_EXPIRED", "INVALID_PIN"]:
            adj = 0.20
            delta += adj
            adjustments.append({"factor": "CUSTOMER_ACTION_REQUIRED", "delta": adj})

        if customer_hist_rate >= 0.80:
            adj = 0.10
            delta += adj
            adjustments.append({"factor": "RESPONSIVE_CUSTOMER_HISTORY", "delta": adj})

        if subscription_flag:
            adj = -0.15
            delta += adj
            adjustments.append({"factor": "UNATTENDED_SUBSCRIPTION_TRANSACTION", "delta": adj})

        if failure_category == "TECHNICAL_TIMEOUT" or failure_code in ["GATEWAY_TIMEOUT", "NETWORK_ERROR"]:
            adj = -0.30
            delta += adj
            adjustments.append({"factor": "INAPPROPRIATE_CUSTOMER_PROMPT_FOR_TECHNICAL_FAILURE", "delta": adj})

    # Strict compliance block
    if failure_code == "RISK_REJECTED" or risk_score > HIGH_RISK_SCORE_THRESHOLD:
        adj = -0.80
        delta += adj
        adjustments.append({"factor": "HIGH_RISK_COMPLIANCE_PENALTY", "delta": adj})

    raw_prob = p_base + delta
    bounded_prob = round(max(0.01, min(0.99, raw_prob)), 4)

    trace = {
        "base_ml_prob": round(p_base, 4),
        "total_delta": round(delta, 4),
        "adjustments": adjustments,
        "raw_prob": round(raw_prob, 4),
        "final_bounded_prob": bounded_prob
    }

    return bounded_prob, trace

def calculate_economic_value(
    strategy: RecoveryStrategy,
    strategy_prob: float,
    transaction_amount: Any,
    transaction_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculates Expected Economic Value using Decimal for exact monetary precision:
    
    Expected Economic Value = P(success) * transaction_amount
                              - recovery_cost
                              - customer_friction_cost
                              - risk_penalty
    """
    amount_dec = to_decimal(transaction_amount)
    prob_dec = Decimal(str(round(strategy_prob, 4)))

    if strategy == RecoveryStrategy.DO_NOT_ACT:
        recovery_cost_dec = Decimal("0.00")
        friction_cost_dec = Decimal("0.00")
        risk_penalty_dec = Decimal("0.00")
        expected_recovery_dec = Decimal("0.00")
        expected_ev_dec = Decimal("0.00")
    else:
        recovery_cost_dec = STRATEGY_BASE_COSTS[strategy]
        friction_cost_dec = STRATEGY_FRICTION_COSTS[strategy]
        
        failure_code = str(transaction_data.get("failure_code", "")).upper()
        risk_score = float(transaction_data.get("risk_score", 0.0))

        if failure_code == "RISK_REJECTED" or risk_score > HIGH_RISK_SCORE_THRESHOLD:
            risk_penalty_dec = Decimal("1000.00")
        else:
            risk_penalty_dec = to_decimal(risk_score * 50.0)

        expected_recovery_dec = (prob_dec * amount_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_ev_dec = (expected_recovery_dec - recovery_cost_dec - friction_cost_dec - risk_penalty_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "transaction_amount": amount_dec,
        "strategy_success_probability": float(prob_dec),
        "expected_recovery": expected_recovery_dec,
        "recovery_cost": recovery_cost_dec,
        "customer_friction_cost": friction_cost_dec,
        "risk_penalty": risk_penalty_dec,
        "expected_economic_value": expected_ev_dec
    }
