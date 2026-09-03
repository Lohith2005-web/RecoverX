from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
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

    scenario_results = []
    for cfg in scenarios_config:
        res = run_what_if_simulation(
            db,
            scenario_name=cfg.get("name", "Unnamed Scenario"),
            scenario_type=cfg.get("type", ScenarioType.CUSTOM_SCENARIO.value),
            gateway_status_overrides=cfg.get("gateway_status_overrides"),
            recoverability_threshold=cfg.get("recoverability_threshold", 0.70),
            strategy_overrides=cfg.get("strategy_overrides"),
            include_baseline=True,
            observation_hours=observation_hours
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
