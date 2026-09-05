import datetime
import json
from typing import Dict, Any, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app.db.models import Transaction, Gateway
from app.engine.baseline_engine import evaluate_naive_baseline_and_recoverx
from app.ml.model_store import predict_recoverability_batch
from app.simulation.constants import ScenarioType
from app.simulation.what_if_engine import run_what_if_simulation


def compare_recovery_scenarios(
    db: Session,
    scenarios_config: Optional[List[Dict[str, Any]]] = None,
    observation_hours: int = 72
) -> Dict[str, Any]:
    """
    Evaluates multiple counterfactual scenarios in a single request.
    Ranks scenarios deterministically by backend-calculated expected_net_recovery.
    Produces machine-readable evidence and objective backend recommendations (NO LLM selection).
    Optimized for ultra-fast batch processing under 0.5s total latency.
    """
    if not scenarios_config:
        # Default benchmark scenarios
        scenarios_config = [
            {
                "name": "Current Conditions",
                "type": ScenarioType.CURRENT_CONDITIONS.value,
                "gateway_status_overrides": {},
                "recoverability_threshold": 0.70
            },
            {
                "name": "Gateway B Remains Degraded",
                "type": ScenarioType.GATEWAY_DEGRADATION.value,
                "gateway_status_overrides": {"gateway_b": "DEGRADED"},
                "recoverability_threshold": 0.70
            },
            {
                "name": "Gateway B Degraded + Gateway Reroute",
                "type": ScenarioType.GATEWAY_REROUTE.value,
                "gateway_status_overrides": {"gateway_b": "DEGRADED"},
                "strategy_overrides": {"GATEWAY_TIMEOUT": "GATEWAY_REROUTE"},
                "recoverability_threshold": 0.70
            },
            {
                "name": "Gateway B Degraded + Stricter Threshold (0.80)",
                "type": ScenarioType.THRESHOLD_ADJUSTMENT.value,
                "gateway_status_overrides": {"gateway_b": "DEGRADED"},
                "recoverability_threshold": 0.80
            }
        ]

    # Pre-fetch failed transactions and gateways ONCE from DB
    latest_ts = db.query(func.max(Transaction.timestamp)).scalar()
    if not latest_ts:
        return {
            "scenarios": [],
            "recommended_scenario": "",
            "recommendation_reason": "No transaction data available",
            "evidence": []
        }

    window_start = latest_ts - datetime.timedelta(hours=observation_hours)
    failed_txns = db.query(Transaction).filter(
        Transaction.timestamp >= window_start,
        Transaction.status == "FAILED"
    ).all()

    gateways = db.query(Gateway).all()
    gtw_map = {g.id: g for g in gateways}

    # Evaluate Naive Baseline ONCE for all counterfactuals
    cached_baseline_eval = evaluate_naive_baseline_and_recoverx(db)

    # ML Prediction cache keyed by gateway status overrides
    ml_cache: Dict[str, List[float]] = {}

    scenario_results = []
    for cfg in scenarios_config:
        gtw_overrides = cfg.get("gateway_status_overrides") or {}
        cache_key = json.dumps(gtw_overrides, sort_keys=True)

        if cache_key not in ml_cache:
            # Build feature rows for batch ML inference
            infer_inputs = []
            for t in failed_txns:
                gtw_obj = gtw_map.get(t.gateway_id)
                gtw_code = gtw_obj.code if gtw_obj else "unknown"
                effective_gtw_status = gtw_overrides.get(gtw_code, gtw_obj.status if gtw_obj else "HEALTHY")

                infer_inputs.append({
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
                    "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                    "gateway_status": effective_gtw_status
                })
            ml_cache[cache_key] = predict_recoverability_batch(infer_inputs)

        p_ml_list = ml_cache[cache_key]

        res = run_what_if_simulation(
            db,
            scenario_name=cfg.get("name", "Unnamed Scenario"),
            scenario_type=cfg.get("type", ScenarioType.CUSTOM_SCENARIO.value),
            gateway_status_overrides=gtw_overrides,
            recoverability_threshold=cfg.get("recoverability_threshold", 0.70),
            strategy_overrides=cfg.get("strategy_overrides"),
            include_baseline=True,
            observation_hours=observation_hours,
            preloaded_failed_txns=failed_txns,
            preloaded_gtw_map=gtw_map,
            preloaded_p_ml_list=p_ml_list,
            preloaded_baseline_eval=cached_baseline_eval
        )
        scenario_results.append(res)


    # Rank scenarios deterministically by expected_net_recovery
    ranked = sorted(
        scenario_results,
        key=lambda x: x.get("metrics", {}).get("expected_net_recovery", 0.0),
        reverse=True
    )

    recommended = ranked[0]
    rec_name = recommended.get("scenario_name", "")
    rec_net = recommended.get("metrics", {}).get("expected_net_recovery", 0.0)
    rec_risk = recommended.get("metrics", {}).get("expected_risk_penalty", 0.0)
    rec_attempts = recommended.get("metrics", {}).get("expected_attempts", 0)

    # Build evidence items for comparison
    evidence_items = []
    for res in scenario_results:
        m = res.get("metrics", {})
        evidence_items.append({
            "type": "scenario_metric",
            "scenario_name": res.get("scenario_name"),
            "expected_net_recovery": m.get("expected_net_recovery"),
            "gross_expected_recovery": m.get("gross_expected_recovery"),
            "expected_attempts": m.get("expected_attempts"),
            "risk_penalty": m.get("expected_risk_penalty"),
            "source": "what_if_engine"
        })

    recommendation_reason = (
        f"Scenario '{rec_name}' yields the highest expected net recovery (₹{rec_net:,.2f}) "
        f"across evaluated counterfactuals, with expected risk penalty of ₹{rec_risk:,.2f} "
        f"over {rec_attempts} recovery attempts."
    )

    return {
        "scenarios": scenario_results,
        "recommended_scenario": rec_name,
        "recommendation_reason": recommendation_reason,
        "evidence": evidence_items
    }
