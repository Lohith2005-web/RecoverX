import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Incident, Anomaly, IncidentTimelineEvent, Gateway, Issuer
from app.incidents.anomaly_detector import detect_payment_anomalies
from app.incidents.incident_manager import (
    process_and_group_incidents,
    compute_incident_revenue_at_risk
)

router = APIRouter()

@router.get("/anomalies")
def list_anomalies(
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Returns list of detected payment system anomalies.
    """
    anoms = db.query(Anomaly).order_by(Anomaly.detected_at.desc()).offset(offset).limit(limit).all()
    total_count = db.query(Anomaly).count()

    results = []
    for a in anoms:
        results.append({
            "id": a.id,
            "metric": a.metric,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "current_value": a.current_value,
            "baseline_value": a.baseline_value,
            "deviation_percent": a.deviation_percent,
            "z_score": a.z_score,
            "severity": a.severity,
            "evidence": json.loads(a.evidence_json) if a.evidence_json else {},
            "detected_at": a.detected_at.isoformat() if a.detected_at else None
        })

    return {
        "total_anomalies": total_count,
        "limit": limit,
        "offset": offset,
        "anomalies": results
    }


@router.post("/anomalies/detect")
def run_anomaly_detection(
    observation_hours: int = Query(72, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Runs statistical anomaly detection across payment dimensions.
    """
    anomalies = detect_payment_anomalies(db, observation_hours=observation_hours)
    return {
        "status": "success",
        "anomalies_detected_count": len(anomalies),
        "anomalies": anomalies
    }


@router.get("/incidents")
def list_incidents(
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE or RESOLVED"),
    status_filter: Optional[str] = Query(None, description="Alias for status filter"),
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW"),
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Returns list of grouped operational incidents with failure rate metrics and financial breakdowns.
    """
    target_status = status or status_filter
    query = db.query(Incident)
    if target_status and isinstance(target_status, str):
        query = query.filter(Incident.status == target_status.upper())
    if severity and isinstance(severity, str):
        query = query.filter(Incident.severity == severity.upper())

    total_count = query.count()
    incidents = query.order_by(Incident.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for inc in incidents:
        results.append({
            "id": inc.id,
            "title": inc.title,
            "incident_type": inc.incident_type,
            "anomaly_type": inc.anomaly_type,
            "severity": inc.severity,
            "status": inc.status,
            "gateway_id": inc.gateway_id,
            "issuer_id": inc.issuer_id,
            "affected_payment_method": inc.affected_payment_method,
            "baseline_rate": inc.baseline_rate,
            "current_rate": inc.current_rate,
            "affected_transactions": inc.affected_transactions,
            "revenue_at_risk": inc.revenue_at_risk,
            "gross_revenue_at_risk": inc.revenue_at_risk,
            "recoverable_revenue_at_risk": inc.recoverable_revenue_at_risk,
            "unrecoverable_revenue_at_risk": inc.unrecoverable_revenue_at_risk,
            "recovered_revenue": inc.recovered_revenue,
            "confidence": inc.confidence,
            "confidence_type": inc.confidence_type,
            "root_cause": inc.root_cause,
            "recommended_action": inc.recommended_action,
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None
        })

    return {
        "total_incidents": total_count,
        "limit": limit,
        "offset": offset,
        "incidents": results
    }


@router.post("/incidents/detect")
def trigger_incident_detection(
    observation_hours: int = Query(72, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Idempotently triggers anomaly detection, incident grouping, revenue-at-risk calculations,
    and Phase 3 recovery integration.
    """
    incidents = process_and_group_incidents(db, observation_hours=observation_hours)
    return {
        "status": "success",
        "incidents_processed_count": len(incidents),
        "incidents": incidents
    }


@router.get("/incidents/{incident_id}")
def get_incident_detail(
    incident_id: str = Path(..., description="ID of the incident"),
    db: Session = Depends(get_db)
):
    """
    Returns detailed view of a single operational incident including evidence and root cause.
    """
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    evidence = json.loads(inc.evidence_json) if inc.evidence_json else {}

    return {
        "id": inc.id,
        "title": inc.title,
        "incident_type": inc.incident_type,
        "anomaly_type": inc.anomaly_type,
        "severity": inc.severity,
        "status": inc.status,
        "gateway_id": inc.gateway_id,
        "issuer_id": inc.issuer_id,
        "affected_payment_method": inc.affected_payment_method,
        "baseline_rate": inc.baseline_rate,
        "current_rate": inc.current_rate,
        "affected_transactions": inc.affected_transactions,
        "gross_revenue_at_risk": inc.revenue_at_risk,
        "revenue_at_risk": inc.revenue_at_risk,
        "recoverable_revenue_at_risk": inc.recoverable_revenue_at_risk,
        "unrecoverable_revenue_at_risk": inc.unrecoverable_revenue_at_risk,
        "recovered_revenue": inc.recovered_revenue,
        "financial_impact": {
            "gross_revenue_at_risk": inc.revenue_at_risk,
            "recoverable_revenue_at_risk": inc.recoverable_revenue_at_risk,
            "unrecoverable_revenue_at_risk": inc.unrecoverable_revenue_at_risk,
            "recovered_revenue": inc.recovered_revenue
        },
        "confidence": inc.confidence,
        "confidence_type": inc.confidence_type,
        "root_cause": inc.root_cause,
        "recommended_action": inc.recommended_action,
        "evidence": evidence,
        "created_at": inc.created_at.isoformat() if inc.created_at else None,
        "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None
    }


@router.get("/incidents/{incident_id}/timeline")
def get_incident_timeline(
    incident_id: str = Path(..., description="ID of the incident"),
    db: Session = Depends(get_db)
):
    """
    Returns structured timeline events for an operational incident.
    """
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    events = db.query(IncidentTimelineEvent).filter(IncidentTimelineEvent.incident_id == incident_id).order_by(IncidentTimelineEvent.timestamp.asc()).all()

    results = []
    for ev in events:
        results.append({
            "id": ev.id,
            "incident_id": ev.incident_id,
            "event_type": ev.event_type,
            "description": ev.description,
            "event_data": json.loads(ev.event_data) if ev.event_data else {},
            "timestamp": ev.timestamp.isoformat() if ev.timestamp else None
        })

    return {
        "incident_id": inc.id,
        "title": inc.title,
        "timeline_events": results
    }


@router.get("/incidents/{incident_id}/impact")
def get_incident_impact(
    incident_id: str = Path(..., description="ID of the incident"),
    db: Session = Depends(get_db)
):
    """
    Returns breakdown of revenue at risk (gross, recoverable, unrecoverable, actual recovered).
    """
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    rev_dict = compute_incident_revenue_at_risk(
        db,
        gateway_id=inc.gateway_id,
        issuer_id=inc.issuer_id,
        payment_method=inc.affected_payment_method
    )

    return {
        "incident_id": inc.id,
        "affected_transactions": rev_dict["affected_count"],
        "gross_revenue_at_risk": float(rev_dict["gross"]),
        "expected_recoverable_revenue_at_risk": float(rev_dict["recoverable"]),
        "expected_unrecoverable_revenue": float(rev_dict["unrecoverable"]),
        "actual_recovered_revenue": float(rev_dict["recovered"])
    }
