from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import Transaction, Gateway, Incident

router = APIRouter()

@router.get("/dashboard/metrics")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """
    Returns authentic financial metrics calculated directly from the database transactions.
    No hardcoded or fabricated numbers.
    """
    total_txns = db.query(func.count(Transaction.id)).scalar() or 0
    if total_txns == 0:
        return {
            "total_transactions": 0,
            "total_transaction_value": 0.0,
            "successful_payment_value": 0.0,
            "failed_payment_value": 0.0,
            "revenue_at_risk": 0.0,
            "ground_truth_recoverable_revenue": 0.0,
            "actual_recovered_revenue": 0.0,
            "overall_failure_rate": 0.0,
            "recovery_rate": 0.0,
            "gateway_performance": [],
            "active_incidents_count": 0
        }

    # Financial sums
    total_val = db.query(func.sum(Transaction.amount)).scalar() or 0.0
    success_val = db.query(func.sum(Transaction.amount)).filter(Transaction.status == "SUCCESS").scalar() or 0.0
    failed_val = db.query(func.sum(Transaction.amount)).filter(Transaction.status == "FAILED").scalar() or 0.0
    recovered_val = db.query(func.sum(Transaction.recovered_amount)).scalar() or 0.0

    # Ground truth recoverable revenue among currently failed transactions
    gt_recoverable_val = db.query(func.sum(Transaction.amount)).filter(
        Transaction.status == "FAILED",
        Transaction.is_recoverable_ground_truth == True
    ).scalar() or 0.0

    # Counts
    failed_count = db.query(func.count(Transaction.id)).filter(Transaction.status == "FAILED").scalar() or 0
    recovered_count = db.query(func.count(Transaction.id)).filter(Transaction.status == "RECOVERED").scalar() or 0

    failure_rate = round(failed_count / total_txns, 4)
    recovery_rate = round(recovered_count / (failed_count + recovered_count), 4) if (failed_count + recovered_count) > 0 else 0.0

    # Gateway performance breakdown
    gateways = db.query(Gateway).all()
    gtw_perf = []
    for g in gateways:
        g_total = db.query(func.count(Transaction.id)).filter(Transaction.gateway_id == g.id).scalar() or 0
        g_failed = db.query(func.count(Transaction.id)).filter(Transaction.gateway_id == g.id, Transaction.status == "FAILED").scalar() or 0
        g_at_risk = db.query(func.sum(Transaction.amount)).filter(Transaction.gateway_id == g.id, Transaction.status == "FAILED").scalar() or 0.0
        g_rate = round(g_failed / g_total if g_total > 0 else 0.0, 4)
        
        gtw_perf.append({
            "gateway_id": g.id,
            "gateway_code": g.code,
            "gateway_name": g.name,
            "status": g.status,
            "total_transactions": g_total,
            "failed_transactions": g_failed,
            "failure_rate": g_rate,
            "baseline_failure_rate": g.baseline_failure_rate,
            "revenue_at_risk": round(g_at_risk, 2)
        })

    # Active incidents
    active_incidents = db.query(Incident).filter(Incident.status == "ACTIVE").all()
    incidents_summary = []
    for inc in active_incidents:
        incidents_summary.append({
            "id": inc.id,
            "title": inc.title,
            "severity": inc.severity,
            "status": inc.status,
            "anomaly_type": inc.anomaly_type,
            "baseline_rate": inc.baseline_rate,
            "current_rate": inc.current_rate,
            "revenue_at_risk": inc.revenue_at_risk,
            "gross_revenue_at_risk": inc.revenue_at_risk,
            "recoverable_revenue_at_risk": inc.recoverable_revenue_at_risk,
            "unrecoverable_revenue_at_risk": inc.unrecoverable_revenue_at_risk,
            "confidence": inc.confidence,
            "root_cause": inc.root_cause
        })

    return {
        "total_transactions": total_txns,
        "failed_transactions_count": failed_count,
        "total_transaction_value": round(total_val, 2),
        "successful_payment_value": round(success_val, 2),
        "failed_payment_value": round(failed_val, 2),
        "revenue_at_risk": round(failed_val, 2),
        "ground_truth_recoverable_revenue": round(gt_recoverable_val, 2),
        "actual_recovered_revenue": round(recovered_val, 2),
        "overall_failure_rate": failure_rate,
        "recovery_rate": recovery_rate,
        "gateway_performance": gtw_perf,
        "active_incidents_count": len(incidents_summary),
        "active_incidents": incidents_summary
    }
