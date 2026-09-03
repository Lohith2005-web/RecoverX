from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.simulation.constants import ScenarioType
from app.simulation.what_if_engine import run_what_if_simulation
from app.simulation.scenario_comparator import compare_recovery_scenarios

router = APIRouter()

class ScenarioRequest(BaseModel):
    name: str = Field("Counterfactual Scenario", description="Name of the scenario")
    type: str = Field("CUSTOM_SCENARIO", description="Scenario type enum")
    gateway_status_overrides: Dict[str, str] = Field(default_factory=dict, description="e.g. {'gateway_b': 'DEGRADED'}")
    recoverability_threshold: float = Field(0.70, ge=0.0, le=1.0, description="Recoverability threshold (0.0 to 1.0)")
    strategy_overrides: Dict[str, str] = Field(default_factory=dict, description="e.g. {'GATEWAY_TIMEOUT': 'GATEWAY_REROUTE'}")
    include_baseline: bool = Field(True, description="Whether to include Naive Baseline comparison")
    observation_hours: int = Field(72, ge=1, le=168, description="Observation window hours")


class ScenarioComparisonRequest(BaseModel):
    scenarios: Optional[List[ScenarioRequest]] = Field(None, description="List of scenarios to evaluate and compare")
    observation_hours: int = Field(72, ge=1, le=168, description="Observation window hours")


@router.post("/simulation/what-if")
def execute_what_if_simulation(
    req: ScenarioRequest,
    db: Session = Depends(get_db)
):
    """
    Executes a pure counterfactual What-If recovery simulation.
    Does NOT mutate transactions, incidents, recovery executions, or scenario state.
    Calculates all metrics with Decimal financial precision.
    """
    scen_type = ScenarioType.CUSTOM_SCENARIO
    try:
        scen_type = ScenarioType(req.type.upper())
    except ValueError:
        pass

    res = run_what_if_simulation(
        db,
        scenario_name=req.name,
        scenario_type=scen_type,
        gateway_status_overrides=req.gateway_status_overrides,
        recoverability_threshold=req.recoverability_threshold,
        strategy_overrides=req.strategy_overrides,
        include_baseline=req.include_baseline,
        observation_hours=req.observation_hours
    )
    return res


@router.post("/simulation/compare")
def compare_scenarios(
    req: ScenarioComparisonRequest,
    db: Session = Depends(get_db)
):
    """
    Evaluates multiple counterfactual scenarios in a single request.
    Ranks scenarios deterministically by backend-calculated expected_net_recovery.
    Produces machine-readable evidence items and backend recommendations.
    """
    cfgs = None
    if req.scenarios:
        cfgs = [s.model_dump() for s in req.scenarios]

    res = compare_recovery_scenarios(
        db,
        scenarios_config=cfgs,
        observation_hours=req.observation_hours
    )
    return res
