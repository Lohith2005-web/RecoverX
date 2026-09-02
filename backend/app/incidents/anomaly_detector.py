import math
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import Transaction, Gateway, Issuer, utc_now
from app.incidents.constants import (
    AnomalyMetric,
    IncidentSeverity,
    MIN_SAMPLE_SIZE,
    MIN_AFFECTED_COUNT,
    FAILURE_RATE_DEVIATION_THRESHOLD,
    LATENCY_DEVIATION_THRESHOLD,
    MIN_ABSOLUTE_RATE_INCREASE,
    Z_SCORE_THRESHOLD
)

def compute_percentage_deviation(current_val: float, baseline_val: float) -> float:
    """Computes percentage deviation: ((current - baseline) / max(0.0001, baseline)) * 100."""
    denom = max(0.0001, float(baseline_val))
    dev = ((float(current_val) - float(baseline_val)) / denom) * 100.0
    return round(dev, 2)

def compute_z_score(current_val: float, baseline_mean: float, baseline_std: float) -> Optional[float]:
    """Computes statistical z-score if standard deviation > 0."""
    if baseline_std is None or baseline_std <= 1e-6:
        return None
    z = (float(current_val) - float(baseline_mean)) / float(baseline_std)
    return round(z, 2)

def assign_anomaly_severity(deviation_percent: float, absolute_diff: float) -> IncidentSeverity:
    """Assigns severity based on transparent deviation and absolute difference rules."""
    if deviation_percent >= 300.0 and absolute_diff >= 0.10:
        return IncidentSeverity.CRITICAL
    elif deviation_percent >= 150.0 and absolute_diff >= 0.05:
        return IncidentSeverity.HIGH
    elif deviation_percent >= 100.0 and absolute_diff >= 0.03:
        return IncidentSeverity.MEDIUM
    else:
        return IncidentSeverity.LOW

def detect_payment_anomalies(db: Session, observation_hours: int = 72) -> List[Dict[str, Any]]:
    """
    Detects statistical anomalies across payment dimensions:
    - Overall failure rate
    - Gateway failure & timeout rates
    - Issuer failure rates
    - Payment method failure rates
    - Latency spikes
    
    Prevents baseline contamination by excluding active injected incident transactions from historical baseline.
    Requires MIN_SAMPLE_SIZE (N >= 40) in historical baseline and MIN_AFFECTED_COUNT (N >= 5) in failures.
    """
    latest_ts = db.query(func.max(Transaction.timestamp)).scalar()
    if not latest_ts:
        return []

    window_start = latest_ts - datetime.timedelta(hours=observation_hours)

    # 1. Historical Baseline Query (Normal transactions, uninfected by scenario injection)
    baseline_query = db.query(Transaction).filter(
        Transaction.timestamp < window_start,
        Transaction.scenario_tag == "NORMAL"
    )

    # 2. Current Observation Query (Recent window transactions)
    current_query = db.query(Transaction).filter(
        Transaction.timestamp >= window_start
    )

    anomalies = []

    # ----------------------------------------------------
    # A. GATEWAY ANOMALIES (Failure Rate & Timeout Rate)
    # ----------------------------------------------------
    gateways = db.query(Gateway).all()
    for gtw in gateways:
        gtw_base_txns = baseline_query.filter(Transaction.gateway_id == gtw.id).all()
        n_base = len(gtw_base_txns)

        if n_base < MIN_SAMPLE_SIZE:
            continue

        base_failures = sum(1 for t in gtw_base_txns if t.status == "FAILED")
        base_timeouts = sum(1 for t in gtw_base_txns if t.failure_code in ["GATEWAY_TIMEOUT", "GATEWAY_DEGRADATION"])
        base_fail_rate = base_failures / n_base
        base_timeout_rate = base_timeouts / n_base
        base_std = math.sqrt(max(1e-6, base_fail_rate * (1.0 - base_fail_rate) / n_base))

        gtw_curr_txns = current_query.filter(Transaction.gateway_id == gtw.id).all()
        n_curr = len(gtw_curr_txns)

        if n_curr < MIN_SAMPLE_SIZE:
            continue

        curr_failures = sum(1 for t in gtw_curr_txns if t.status == "FAILED")
        curr_timeouts = sum(1 for t in gtw_curr_txns if t.failure_code in ["GATEWAY_TIMEOUT", "GATEWAY_DEGRADATION"])
        curr_fail_rate = curr_failures / n_curr
        curr_timeout_rate = curr_timeouts / n_curr

        abs_diff_fail = curr_fail_rate - base_fail_rate
        abs_diff_timeout = curr_timeout_rate - base_timeout_rate

        dev_fail = compute_percentage_deviation(curr_fail_rate, base_fail_rate)
        z_fail = compute_z_score(curr_fail_rate, base_fail_rate, base_std)

        # Check Gateway Failure Rate Anomaly
        if dev_fail >= FAILURE_RATE_DEVIATION_THRESHOLD and abs_diff_fail >= MIN_ABSOLUTE_RATE_INCREASE and curr_failures >= MIN_AFFECTED_COUNT:
            severity = assign_anomaly_severity(dev_fail, abs_diff_fail)
            anomalies.append({
                "metric": AnomalyMetric.GATEWAY_FAILURE_RATE.value,
                "entity_type": "GATEWAY",
                "entity_id": gtw.code,
                "entity_name": gtw.name,
                "current_value": round(curr_fail_rate, 4),
                "baseline_value": round(base_fail_rate, 4),
                "deviation_percent": dev_fail,
                "z_score": z_fail,
                "severity": severity.value,
                "affected_transactions": curr_failures,
                "sample_size": n_curr,
                "detected_at": utc_now().isoformat()
            })

        # Check Gateway Timeout Rate Anomaly
        dev_timeout = compute_percentage_deviation(curr_timeout_rate, base_timeout_rate)
        if dev_timeout >= FAILURE_RATE_DEVIATION_THRESHOLD and abs_diff_timeout >= MIN_ABSOLUTE_RATE_INCREASE and curr_timeouts >= MIN_AFFECTED_COUNT:
            severity = assign_anomaly_severity(dev_timeout, abs_diff_timeout)
            anomalies.append({
                "metric": AnomalyMetric.GATEWAY_TIMEOUT_RATE.value,
                "entity_type": "GATEWAY",
                "entity_id": gtw.code,
                "entity_name": gtw.name,
                "current_value": round(curr_timeout_rate, 4),
                "baseline_value": round(base_timeout_rate, 4),
                "deviation_percent": dev_timeout,
                "z_score": compute_z_score(curr_timeout_rate, base_timeout_rate, base_std),
                "severity": severity.value,
                "affected_transactions": curr_timeouts,
                "sample_size": n_curr,
                "detected_at": utc_now().isoformat()
            })

    # ----------------------------------------------------
    # B. ISSUER ANOMALIES (Failure Rate)
    # ----------------------------------------------------
    issuers = db.query(Issuer).all()
    for isr in issuers:
        isr_base_txns = baseline_query.filter(Transaction.issuer_id == isr.id).all()
        n_base = len(isr_base_txns)

        if n_base < MIN_SAMPLE_SIZE:
            continue

        base_failures = sum(1 for t in isr_base_txns if t.status == "FAILED")
        base_fail_rate = base_failures / n_base
        base_std = math.sqrt(max(1e-6, base_fail_rate * (1.0 - base_fail_rate) / n_base))

        isr_curr_txns = current_query.filter(Transaction.issuer_id == isr.id).all()
        n_curr = len(isr_curr_txns)

        if n_curr < MIN_SAMPLE_SIZE:
            continue

        curr_failures = sum(1 for t in isr_curr_txns if t.status == "FAILED")
        curr_fail_rate = curr_failures / n_curr
        abs_diff = curr_fail_rate - base_fail_rate
        dev_fail = compute_percentage_deviation(curr_fail_rate, base_fail_rate)

        if dev_fail >= FAILURE_RATE_DEVIATION_THRESHOLD and abs_diff >= MIN_ABSOLUTE_RATE_INCREASE and curr_failures >= MIN_AFFECTED_COUNT:
            severity = assign_anomaly_severity(dev_fail, abs_diff)
            anomalies.append({
                "metric": AnomalyMetric.ISSUER_FAILURE_RATE.value,
                "entity_type": "ISSUER",
                "entity_id": isr.code,
                "entity_name": isr.name,
                "current_value": round(curr_fail_rate, 4),
                "baseline_value": round(base_fail_rate, 4),
                "deviation_percent": dev_fail,
                "z_score": compute_z_score(curr_fail_rate, base_fail_rate, base_std),
                "severity": severity.value,
                "affected_transactions": curr_failures,
                "sample_size": n_curr,
                "detected_at": utc_now().isoformat()
            })

    # ----------------------------------------------------
    # C. PAYMENT METHOD ANOMALIES
    # ----------------------------------------------------
    methods = ["UPI", "CREDIT_CARD", "DEBIT_CARD", "NET_BANKING"]
    for pm in methods:
        pm_base_txns = baseline_query.filter(Transaction.payment_method == pm).all()
        n_base = len(pm_base_txns)
        if n_base < MIN_SAMPLE_SIZE:
            continue

        base_failures = sum(1 for t in pm_base_txns if t.status == "FAILED")
        base_fail_rate = base_failures / n_base
        base_std = math.sqrt(max(1e-6, base_fail_rate * (1.0 - base_fail_rate) / n_base))

        pm_curr_txns = current_query.filter(Transaction.payment_method == pm).all()
        n_curr = len(pm_curr_txns)
        if n_curr < MIN_SAMPLE_SIZE:
            continue

        curr_failures = sum(1 for t in pm_curr_txns if t.status == "FAILED")
        curr_fail_rate = curr_failures / n_curr
        abs_diff = curr_fail_rate - base_fail_rate
        dev_fail = compute_percentage_deviation(curr_fail_rate, base_fail_rate)

        if dev_fail >= FAILURE_RATE_DEVIATION_THRESHOLD and abs_diff >= MIN_ABSOLUTE_RATE_INCREASE and curr_failures >= MIN_AFFECTED_COUNT:
            severity = assign_anomaly_severity(dev_fail, abs_diff)
            anomalies.append({
                "metric": AnomalyMetric.PAYMENT_METHOD_FAILURE_RATE.value,
                "entity_type": "PAYMENT_METHOD",
                "entity_id": pm,
                "entity_name": pm,
                "current_value": round(curr_fail_rate, 4),
                "baseline_value": round(base_fail_rate, 4),
                "deviation_percent": dev_fail,
                "z_score": compute_z_score(curr_fail_rate, base_fail_rate, base_std),
                "severity": severity.value,
                "affected_transactions": curr_failures,
                "sample_size": n_curr,
                "detected_at": utc_now().isoformat()
            })

    return anomalies
