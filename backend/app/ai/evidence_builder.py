import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.db.models import Transaction, Incident, Gateway, Issuer, IncidentTimelineEvent, Anomaly
from app.ml.model_store import predict_recoverability
from app.engine.strategy_selector import evaluate_recovery_decision
from app.simulation.scenario_comparator import compare_recovery_scenarios
from app.ai.constants import InvestigationType

def build_transaction_evidence(db: Session, transaction_id: str) -> Dict[str, Any]:
    """Retrieves ground-truth context and builds structured evidence for a Transaction."""
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        return {
            "error": f"Transaction '{transaction_id}' not found.",
            "investigation_type": InvestigationType.TRANSACTION_INVESTIGATION.value,
            "evidence": []
        }

    gtw = db.query(Gateway).filter(Gateway.id == txn.gateway_id).first()
    isr = db.query(Issuer).filter(Issuer.id == txn.issuer_id).first()

    infer_input = {
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
        "timestamp": txn.timestamp.isoformat() if txn.timestamp else None,
        "gateway_status": gtw.status if gtw else "HEALTHY"
    }

    ml_pred = predict_recoverability(infer_input)
    p_ml = ml_pred["recoverability_probability"]

    decision = evaluate_recovery_decision(p_ml, float(txn.amount), infer_input)

    evidence_items = [
        {
            "type": "transaction_metric",
            "metric": "amount",
            "value": float(txn.amount),
            "source": f"transactions.id={txn.id}"
        },
        {
            "type": "ml_prediction",
            "metric": "recoverability_probability",
            "value": round(p_ml, 4),
            "source": "ml_model.joblib"
        },
        {
            "type": "economic_decision",
            "strategy": decision["strategy"],
            "expected_economic_value": decision["expected_economic_value"],
            "strategy_success_probability": decision["strategy_success_probability"],
            "autonomy_action": decision["autonomy_action"],
            "confidence": decision["decision_confidence"],
            "confidence_type": decision["confidence_type"],
            "source": "economic_recovery_decision_engine"
        }
    ]

    ground_truth = {
        "id": txn.id,
        "amount": float(txn.amount),
        "status": txn.status,
        "gateway_code": gtw.code if gtw else "unknown",
        "gateway_status": gtw.status if gtw else "HEALTHY",
        "issuer_code": isr.code if isr else "unknown",
        "payment_method": txn.payment_method,
        "failure_code": txn.failure_code,
        "failure_category": txn.failure_category,
        "customer_historical_success_rate": txn.customer_historical_success_rate,
        "ml_recoverability_probability": round(p_ml, 4),
        "selected_strategy": decision["strategy"],
        "expected_economic_value": decision["expected_economic_value"],
        "autonomy_action": decision["autonomy_action"],
        "decision_confidence": decision["decision_confidence"],
        "confidence_type": decision["confidence_type"],
        "explanation": decision["explanation"],
        "alternative_evaluations": decision.get("all_evaluations", [])
    }

    return {
        "investigation_type": InvestigationType.TRANSACTION_INVESTIGATION.value,
        "entity_id": txn.id,
        "ground_truth_context": ground_truth,
        "evidence": evidence_items
    }


def build_incident_evidence(db: Session, incident_id: str) -> Dict[str, Any]:
    """Retrieves ground-truth context and builds structured evidence for an Incident."""
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        return {
            "error": f"Incident '{incident_id}' not found.",
            "investigation_type": InvestigationType.INCIDENT_INVESTIGATION.value,
            "evidence": []
        }

    evidence_json = json.loads(inc.evidence_json) if inc.evidence_json else {}
    timeline_events = db.query(IncidentTimelineEvent).filter(IncidentTimelineEvent.incident_id == incident_id).order_by(IncidentTimelineEvent.timestamp.asc()).all()

    tl_list = []
    for ev in timeline_events:
        tl_list.append({
            "event_type": ev.event_type,
            "description": ev.description,
            "timestamp": ev.timestamp.isoformat() if ev.timestamp else None
        })

    evidence_items = [
        {
            "type": "incident_metric",
            "metric": inc.anomaly_type,
            "value": inc.current_rate,
            "baseline": inc.baseline_rate,
            "severity": inc.severity,
            "source": f"incidents.id={inc.id}"
        },
        {
            "type": "root_cause_evidence",
            "root_cause": inc.root_cause,
            "confidence": inc.confidence,
            "confidence_type": inc.confidence_type,
            "reason_codes": evidence_json.get("reason_codes", []),
            "source": "root_cause_engine"
        },
        {
            "type": "financial_impact",
            "gross_revenue_at_risk": inc.revenue_at_risk,
            "recoverable_revenue_at_risk": inc.recoverable_revenue_at_risk,
            "unrecoverable_revenue_at_risk": inc.unrecoverable_revenue_at_risk,
            "recovered_revenue": inc.recovered_revenue,
            "source": "decimal_impact_engine"
        }
    ]

    ground_truth = {
        "id": inc.id,
        "title": inc.title,
        "incident_type": inc.incident_type,
        "severity": inc.severity,
        "status": inc.status,
        "affected_entity": inc.affected_payment_method or inc.gateway_id or inc.issuer_id or "system",
        "anomaly_type": inc.anomaly_type,
        "baseline_rate": inc.baseline_rate,
        "current_rate": inc.current_rate,
        "affected_transactions": inc.affected_transactions,
        "financial_impact": {
            "gross_revenue_at_risk": inc.revenue_at_risk,
            "recoverable_revenue_at_risk": inc.recoverable_revenue_at_risk,
            "unrecoverable_revenue_at_risk": inc.unrecoverable_revenue_at_risk,
            "recovered_revenue": inc.recovered_revenue
        },
        "root_cause": inc.root_cause,
        "confidence": inc.confidence,
        "confidence_type": inc.confidence_type,
        "recommended_action": inc.recommended_action,
        "timeline_events": tl_list
    }

    return {
        "investigation_type": InvestigationType.INCIDENT_INVESTIGATION.value,
        "entity_id": inc.id,
        "ground_truth_context": ground_truth,
        "evidence": evidence_items
    }


def build_what_if_evidence(db: Session, scenarios_config: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Runs counterfactual What-If simulation engine and builds evidence payload."""
    comp_res = compare_recovery_scenarios(db, scenarios_config=scenarios_config)

    evidence_items = comp_res.get("evidence", [])
    ground_truth = {
        "scenarios": comp_res.get("scenarios", []),
        "recommended_scenario": comp_res.get("recommended_scenario"),
        "recommendation_reason": comp_res.get("recommendation_reason")
    }

    return {
        "investigation_type": InvestigationType.WHAT_IF_EXPLANATION.value,
        "entity_id": "what_if_simulation",
        "ground_truth_context": ground_truth,
        "evidence": evidence_items
    }
