from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.simulator.scenario_engine import inject_gateway_degradation, reset_simulator

router = APIRouter()

@router.post("/simulator/reset")
def reset_demo_simulator(db: Session = Depends(get_db)):
    """
    Resets the database simulator to the original pristine seed state (50,000 transactions).
    """
    res = reset_simulator(db)
    return res

@router.post("/simulator/scenario")
def inject_scenario(
    scenario_type: str = Body(..., embed=True),
    target_gateway: str = Body("gateway_b", embed=True),
    db: Session = Depends(get_db)
):
    """
    Injects a failure scenario into the transaction dataset.
    Supported scenario_type: GATEWAY_DEGRADATION
    """
    if scenario_type == "GATEWAY_DEGRADATION":
        res = inject_gateway_degradation(db, gateway_code=target_gateway)
        return res
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported scenario_type '{scenario_type}'. Supported: 'GATEWAY_DEGRADATION'."
        )
