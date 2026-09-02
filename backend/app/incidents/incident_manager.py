import json
import uuid
import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import (
    Transaction,
    Gateway,
    Issuer,
    Incident,
    Anomaly,
    IncidentTimelineEvent,
    utc_now
)
from app.engine.economic_model import to_decimal
from app.ml.model_store import predict_recoverability
from app.incidents.constants import (
    IncidentSeverity,
    IncidentStatus,
    TimelineEventType
)
from app.incidents.anomaly_detector import detect_payment_anomalies
from app.incidents.root_cause_engine import analyze_root_cause

def compute_incident_revenue_at_risk(
    db: Session,
    gateway_id: Optional[str] = None,
    issuer_id: Optional[str] = None,
    payment_method: Optional[str] = None,
    observation_hours: int = 72
) -> Dict[str, Decimal]:
    """
    Computes revenue at risk breakdown using Decimal precision:
    - gross_revenue_at_risk
    - expected_recoverable_revenue_at_risk (using Phase 2 ML recoverability prob)
    - expected_unrecoverable_revenue
    - actual_recovered_revenue
    """
    latest_ts = db.query(func.max(Transaction.timestamp)).scalar()
    if not latest_ts:
        return {
            "gross": Decimal("0.00"),
            "recoverable": Decimal("0.00"),
            "unrecoverable": Decimal("0.00"),
            "recovered": Decimal("0.00"),
            "affected_count": 0
        }

    window_start = latest_ts - datetime.timedelta(hours=observation_hours)

    query = db.query(Transaction).filter(
        Transaction.timestamp >= window_start,
        Transaction.status.in_(["FAILED", "RECOVERED"])
    )

    if gateway_id:
        query = query.filter(Transaction.gateway_id == gateway_id)
    if issuer_id:
        query = query.filter(Transaction.issuer_id == issuer_id)
    if payment_method:
        query = query.filter(Transaction.payment_method == payment_method)

    affected_txns = query.all()

    gross_dec = Decimal("0.00")
    recoverable_dec = Decimal("0.00")
    recovered_dec = Decimal("0.00")

    for t in affected_txns:
        amount_dec = to_decimal(t.amount)
        if t.status == "FAILED":
            gross_dec += amount_dec
            
            # Predict ML recoverability
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
                "timestamp": t.timestamp.isoformat() if t.timestamp else None
            }
            ml_pred = predict_recoverability(infer_input)
            p_ml_dec = Decimal(str(round(ml_pred["recoverability_probability"], 4)))
            
            rec_val = (amount_dec * p_ml_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            recoverable_dec += rec_val
        elif t.status == "RECOVERED":
            recovered_dec += to_decimal(t.recovered_amount)

    unrecoverable_dec = (gross_dec - recoverable_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "gross": gross_dec,
        "recoverable": recoverable_dec,
        "unrecoverable": max(Decimal("0.00"), unrecoverable_dec),
        "recovered": recovered_dec,
        "affected_count": len(affected_txns)
    }


def process_and_group_incidents(db: Session, observation_hours: int = 72) -> List[Dict[str, Any]]:
    """
    Runs anomaly detection, groups related anomalies into unified Incidents,
    computes Decimal revenue at risk, updates gateway health, and logs timeline events.
    
    IDEMPOTENT: Updates existing ACTIVE incidents for the same entity instead of creating duplicates.
    """
    anomalies_data = detect_payment_anomalies(db, observation_hours=observation_hours)
    
    # Save Anomalies to DB
    for a in anomalies_data:
        anom_record = Anomaly(
            id=f"anom_{uuid.uuid4().hex[:10]}",
            metric=a["metric"],
            entity_type=a["entity_type"],
            entity_id=a["entity_id"],
            current_value=a["current_value"],
            baseline_value=a["baseline_value"],
            deviation_percent=a["deviation_percent"],
            z_score=a.get("z_score"),
            severity=a["severity"],
            evidence_json=json.dumps(a),
            detected_at=utc_now()
        )
        db.add(anom_record)
    db.commit()

    if not anomalies_data:
        return []

    # Group anomalies by Entity (e.g. Gateway, Issuer, Payment Method)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for a in anomalies_data:
        key = f"{a['entity_type']}:{a['entity_id']}"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(a)

    incidents_processed = []

    for key, entity_anomalies in grouped.items():
        primary_anom = max(entity_anomalies, key=lambda x: x["deviation_percent"])
        entity_type = primary_anom["entity_type"]
        entity_id = primary_anom["entity_id"]

        gateway_obj = None
        issuer_obj = None
        gateway_id = None
        issuer_id = None
        payment_method = None

        if entity_type == "GATEWAY":
            gateway_obj = db.query(Gateway).filter(Gateway.code == entity_id).first()
            gateway_id = gateway_obj.id if gateway_obj else None
        elif entity_type == "ISSUER":
            issuer_obj = db.query(Issuer).filter(Issuer.code == entity_id).first()
            issuer_id = issuer_obj.id if issuer_obj else None
        elif entity_type == "PAYMENT_METHOD":
            payment_method = entity_id

        # Compute Decimal Revenue at Risk
        rev_risk = compute_incident_revenue_at_risk(
            db,
            gateway_id=gateway_id,
            issuer_id=issuer_id,
            payment_method=payment_method,
            observation_hours=observation_hours
        )

        # Get affected transactions sample for root cause engine
        query = db.query(Transaction).filter(Transaction.status == "FAILED")
        if gateway_id:
            query = query.filter(Transaction.gateway_id == gateway_id)
        if issuer_id:
            query = query.filter(Transaction.issuer_id == issuer_id)
        sample_txns = query.limit(50).all()

        # Perform Deterministic Root Cause Analysis
        rc_info = analyze_root_cause(primary_anom, anomalies_data, sample_txns)

        # Build machine-readable evidence payload
        evidence_list = []
        for anom in entity_anomalies:
            evidence_list.append({
                "metric": anom["metric"],
                "current": anom["current_value"],
                "baseline": anom["baseline_value"],
                "deviation_percent": anom["deviation_percent"],
                "z_score": anom.get("z_score")
            })
        evidence_list.append({"metric": "affected_transactions", "value": rev_risk["affected_count"]})
        evidence_list.append({"metric": "gross_revenue_at_risk", "value": str(rev_risk["gross"])})

        evidence_payload = {
            "evidence": evidence_list,
            "reason_codes": rc_info["reason_codes"],
            "primary_anomaly": primary_anom
        }

        # IDEMPOTENCY CHECK: Check if ACTIVE incident exists for this entity
        existing_inc = None
        if gateway_id:
            existing_inc = db.query(Incident).filter(Incident.gateway_id == gateway_id, Incident.status == "ACTIVE").first()
        elif issuer_id:
            existing_inc = db.query(Incident).filter(Incident.issuer_id == issuer_id, Incident.status == "ACTIVE").first()
        elif payment_method:
            existing_inc = db.query(Incident).filter(Incident.affected_payment_method == payment_method, Incident.status == "ACTIVE").first()

        if existing_inc:
            # Update existing active incident idempotently
            incident = existing_inc
            incident.current_rate = primary_anom["current_value"]
            incident.affected_transactions = rev_risk["affected_count"]
            incident.revenue_at_risk = float(rev_risk["gross"])
            incident.recoverable_revenue_at_risk = float(rev_risk["recoverable"])
            incident.unrecoverable_revenue_at_risk = float(rev_risk["unrecoverable"])
            incident.recovered_revenue = float(rev_risk["recovered"])
            incident.evidence_json = json.dumps(evidence_payload)
            db.commit()
        else:
            # Create new incident record
            inc_id = f"inc_{int(utc_now().timestamp())}_{uuid.uuid4().hex[:4]}"
            title = f"🚨 Incident: {entity_type} {entity_id.upper()} {primary_anom['metric'].replace('_', ' ')} Spike"
            
            incident = Incident(
                id=inc_id,
                title=title,
                incident_type=rc_info["incident_type"],
                severity=primary_anom["severity"],
                gateway_id=gateway_id,
                issuer_id=issuer_id,
                affected_payment_method=payment_method,
                anomaly_type=primary_anom["metric"],
                baseline_rate=primary_anom["baseline_value"],
                current_rate=primary_anom["current_value"],
                affected_transactions=rev_risk["affected_count"],
                revenue_at_risk=float(rev_risk["gross"]),
                recoverable_revenue_at_risk=float(rev_risk["recoverable"]),
                unrecoverable_revenue_at_risk=float(rev_risk["unrecoverable"]),
                recovered_revenue=float(rev_risk["recovered"]),
                confidence=rc_info["confidence"],
                confidence_type="heuristic",
                root_cause=rc_info["root_cause_summary"],
                recommended_action=rc_info["recommended_action"],
                evidence_json=json.dumps(evidence_payload),
                status="ACTIVE",
                created_at=utc_now()
            )
            db.add(incident)
            db.commit()

            # Create initial Timeline Events for new incident
            t1 = IncidentTimelineEvent(
                id=f"tle_{uuid.uuid4().hex[:10]}",
                incident_id=incident.id,
                event_type=TimelineEventType.INCIDENT_STARTED.value,
                description=f"Operational anomaly detected on {entity_type} {entity_id}.",
                event_data=json.dumps(primary_anom),
                timestamp=utc_now()
            )
            t2 = IncidentTimelineEvent(
                id=f"tle_{uuid.uuid4().hex[:10]}",
                incident_id=incident.id,
                event_type=TimelineEventType.ROOT_CAUSE_IDENTIFIED.value,
                description=rc_info["root_cause_summary"],
                event_data=json.dumps({"reason_codes": rc_info["reason_codes"]}),
                timestamp=utc_now()
            )
            t3 = IncidentTimelineEvent(
                id=f"tle_{uuid.uuid4().hex[:10]}",
                incident_id=incident.id,
                event_type=TimelineEventType.RECOVERY_RECOMMENDATIONS_GENERATED.value,
                description=rc_info["recommended_action"],
                event_data=json.dumps({"recoverable_revenue": str(rev_risk["recoverable"])}),
                timestamp=utc_now()
            )
            db.add_all([t1, t2, t3])
            db.commit()

        # PHASE 3 INTEGRATION: Update Gateway Status to DEGRADED
        # Phase 3 Economic Engine sees gateway.status == 'DEGRADED', making Gateway Reroute economically preferred naturally!
        if gateway_obj and gateway_obj.status != "DEGRADED":
            gateway_obj.status = "DEGRADED"
            db.commit()

        incidents_processed.append({
            "id": incident.id,
            "title": incident.title,
            "incident_type": incident.incident_type,
            "severity": incident.severity,
            "status": incident.status,
            "affected_entity": f"{entity_type}:{entity_id}",
            "affected_transactions": incident.affected_transactions,
            "gross_revenue_at_risk": incident.revenue_at_risk,
            "recoverable_revenue_at_risk": incident.recoverable_revenue_at_risk,
            "unrecoverable_revenue_at_risk": incident.unrecoverable_revenue_at_risk,
            "recovered_revenue": incident.recovered_revenue,
            "confidence": incident.confidence,
            "confidence_type": incident.confidence_type,
            "root_cause": incident.root_cause,
            "recommended_action": incident.recommended_action,
            "evidence": evidence_payload,
            "created_at": incident.created_at.isoformat()
        })

    return incidents_processed
