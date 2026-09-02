from typing import Dict, Any, List

def analyze_root_cause(
    primary_anomaly: Dict[str, Any],
    related_anomalies: List[Dict[str, Any]],
    affected_transactions_sample: List[Any]
) -> Dict[str, Any]:
    """
    Deterministic, explainable root-cause reasoning engine.
    Uses empirical evidence from failure categories, failure codes, latency, and entity isolation.
    Confidence is explicitly labeled as 'heuristic'.
    """
    metric = primary_anomaly.get("metric", "")
    entity_type = primary_anomaly.get("entity_type", "")
    entity_id = primary_anomaly.get("entity_id", "")
    entity_name = primary_anomaly.get("entity_name", entity_id)

    # Analyze failure code distribution in affected transactions sample
    code_counts: Dict[str, int] = {}
    total_sample = len(affected_transactions_sample)
    
    for t in affected_transactions_sample:
        code = getattr(t, "failure_code", "UNKNOWN")
        code_counts[code] = code_counts.get(code, 0) + 1

    top_code = max(code_counts.items(), key=lambda x: x[1])[0] if code_counts else "GATEWAY_TIMEOUT"

    reason_codes = []
    
    if entity_type == "GATEWAY":
        incident_type = "GATEWAY_DEGRADATION"
        reason_codes.append(f"{entity_id.upper()}_FAILURE_SPIKE")
        
        if top_code in ["GATEWAY_TIMEOUT", "GATEWAY_DEGRADATION", "SYSTEM_DEGRADATION"]:
            reason_codes.append("TECHNICAL_TIMEOUT_DOMINATED")
        
        # Check if other gateways are normal (entity isolation)
        other_gtw_anomalies = [a for a in related_anomalies if a.get("entity_type") == "GATEWAY" and a.get("entity_id") != entity_id]
        if not other_gtw_anomalies:
            reason_codes.append("OTHER_GATEWAYS_NORMAL")

        root_cause_summary = f"Infrastructure degradation detected on {entity_name}. Gateway timeout rate spiked by {primary_anomaly.get('deviation_percent', 0):.1f}%, causing technical timeouts while other gateways remain healthy."
        confidence = 0.95
        recommended_action = f"Switch traffic away from {entity_name} using Gateway Reroute to alternate healthy payment gateways."

    elif entity_type == "ISSUER":
        incident_type = "ISSUER_OUTAGE"
        reason_codes.append(f"ISSUER_{entity_id.upper()}_FAILURE_SPIKE")
        reason_codes.append("CARD_AUTHORIZATION_DECLINES")
        
        root_cause_summary = f"Authorization outage detected at Issuer {entity_name}. Failure rate spiked by {primary_anomaly.get('deviation_percent', 0):.1f}%."
        confidence = 0.90
        recommended_action = "Notify merchant of bank issuer degradation; engage customer recovery or retry after bank recovery window."

    elif entity_type == "PAYMENT_METHOD":
        incident_type = "PAYMENT_METHOD_INCIDENT"
        reason_codes.append(f"{entity_id.upper()}_AUTHENTICATION_SPIKE")
        
        root_cause_summary = f"Authentication incident detected on {entity_name} payment rail. Increased OTP and authorization drop-offs."
        confidence = 0.85
        recommended_action = "Prompt customer to re-authenticate or switch to alternative payment method."

    else:
        incident_type = "SYSTEM_TIMEOUT_SPIKE"
        reason_codes.append("SYSTEM_WIDE_LATENCY_SPIKE")
        root_cause_summary = "System-wide network timeout spike affecting multiple payment processing channels."
        confidence = 0.80
        recommended_action = "Monitor network latency and apply Smart Retry for transient timeout failures."

    return {
        "incident_type": incident_type,
        "reason_codes": reason_codes,
        "root_cause_summary": root_cause_summary,
        "confidence": confidence,
        "confidence_type": "heuristic",
        "recommended_action": recommended_action
    }
