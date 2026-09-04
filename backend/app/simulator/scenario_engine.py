import random
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import Transaction, Gateway, Incident, SimulationScenario
from app.simulator.generator import seed_database
from app.config import settings

def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

def inject_gateway_degradation(db: Session, gateway_code: str = "gateway_b") -> dict:
    """
    Injects a realistic Gateway Degradation scenario for the specified gateway (e.g. Gateway B).
    Spikes failure rate from ~2.2% up to ~14.8% by marking technical gateway degradation failures
    on recent transactions. Creates an active Incident record with calculated revenue at risk.
    """
    gateway = db.query(Gateway).filter(Gateway.code == gateway_code).first()
    if not gateway:
        raise ValueError(f"Gateway with code '{gateway_code}' not found.")

    # 1. Update scenario and gateway status
    gateway.status = "DEGRADED"
    
    scenario = db.query(SimulationScenario).filter(SimulationScenario.target_gateway == gateway.id).first()
    if scenario:
        scenario.is_active = True
        scenario.injected_at = utc_now()

    # 2. Get recent Gateway B transactions (last 3 days of generated dataset)
    latest_txn = db.query(func.max(Transaction.timestamp)).scalar()
    if not latest_txn:
        return {"status": "error", "message": "No transactions found in database."}

    window_start = latest_txn - datetime.timedelta(days=3)

    gtw_txns = db.query(Transaction).filter(
        Transaction.gateway_id == gateway.id,
        Transaction.timestamp >= window_start,
        Transaction.status == "SUCCESS"
    ).all()

    # Target: convert ~13% of successful transactions on Gateway B during this window to FAILED due to degradation
    degrade_count = int(len(gtw_txns) * 0.13)
    random.seed(settings.SEED)
    selected_txns = random.sample(gtw_txns, min(degrade_count, len(gtw_txns)))

    total_revenue_impact = 0.0
    recoverable_revenue_impact = 0.0

    for txn in selected_txns:
        txn.status = "FAILED"
        txn.failure_code = "GATEWAY_TIMEOUT"
        txn.failure_category = "TECHNICAL_TIMEOUT"
        txn.scenario_tag = "GATEWAY_B_DEGRADATION"
        txn.latency_ms = int(txn.latency_ms * 4.5) # latency spike

        # Technical gateway degradation is highly recoverable by rerouting!
        txn.is_recoverable_ground_truth = txn.customer_historical_success_rate >= 0.60
        total_revenue_impact += txn.amount
        if txn.is_recoverable_ground_truth:
            recoverable_revenue_impact += txn.amount

    unrecoverable_revenue_impact = total_revenue_impact - recoverable_revenue_impact
    db.commit()

    # 3. Calculate baseline vs current failure rates for Gateway B
    total_gtw_b = db.query(Transaction).filter(Transaction.gateway_id == gateway.id).count()
    failed_gtw_b = db.query(Transaction).filter(Transaction.gateway_id == gateway.id, Transaction.status == "FAILED").count()
    current_failure_rate = round(failed_gtw_b / total_gtw_b if total_gtw_b > 0 else 0.0, 4)

    # 4. Create Incident record
    incident = Incident(
        id=f"inc_{int(utc_now().timestamp())}",
        title=f"🚨 Critical Anomaly: {gateway.name} Failure Rate Spike",
        severity="CRITICAL",
        gateway_id=gateway.id,
        anomaly_type="GATEWAY_DEGRADATION",
        baseline_rate=gateway.baseline_failure_rate,
        current_rate=current_failure_rate,
        affected_transactions=len(selected_txns),
        revenue_at_risk=round(total_revenue_impact, 2),
        recoverable_revenue_at_risk=round(recoverable_revenue_impact, 2),
        unrecoverable_revenue_at_risk=round(unrecoverable_revenue_impact, 2),
        confidence=0.96,
        root_cause=f"Infrastructure degradation detected on {gateway.name}. Latency increased by 350%, causing gateway timeouts and system degradation errors.",
        evidence_json=f'{{"affected_transactions": {len(selected_txns)}, "baseline_rate": {gateway.baseline_failure_rate}, "current_rate": {current_failure_rate}, "revenue_at_risk": {round(total_revenue_impact, 2)}, "recoverable_revenue_at_risk": {round(recoverable_revenue_impact, 2)}}}',
        status="ACTIVE",
        created_at=utc_now()
    )
    db.add(incident)
    db.commit()

    return {
        "status": "success",
        "scenario": "GATEWAY_DEGRADATION",
        "target_gateway": gateway.code,
        "affected_transactions": len(selected_txns),
        "new_failure_rate": current_failure_rate,
        "revenue_at_risk": round(total_revenue_impact, 2),
        "incident_id": incident.id
    }


def reset_simulator(db: Session) -> dict:
    """
    Resets the simulator database to the pristine 50,000 baseline transactions (seed 42).
    """
    res = seed_database(db, num_transactions=settings.DEFAULT_NUM_TRANSACTIONS, seed=settings.SEED)
    return {
        "status": "success",
        "message": "Simulator reset to baseline 50,000 synthetic transactions.",
        "details": res
    }
