from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ai.constants import InvestigationType
from app.ai.investigation_router import route_and_investigate_query
from app.ai.evidence_builder import build_transaction_evidence, build_incident_evidence
from app.ai.providers import GeminiLLMProvider
from app.ai.prompts import SYSTEM_INVESTIGATION_PROMPT

router = APIRouter()

class InvestigationQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language question, e.g. 'Why did RecoverX choose gateway reroute?'")
    investigation_type: Optional[str] = Field(None, description="Optional explicit investigation type enum")
    entity_id: Optional[str] = Field(None, description="Optional target entity ID (e.g. txn_002963 or inc_1234)")
    scenarios_config: Optional[List[Dict[str, Any]]] = Field(None, description="Optional scenario configuration list")


@router.post("/investigation/query")
def process_investigation_query(
    req: InvestigationQueryRequest,
    db: Session = Depends(get_db)
):
    """
    Handles natural language AI investigation queries.
    Retrieves ground-truth backend context, builds structured evidence, and returns an evidence-grounded explanation.
    """
    inv_type = None
    if req.investigation_type:
        try:
            inv_type = InvestigationType(req.investigation_type.upper())
        except ValueError:
            pass

    res = route_and_investigate_query(
        db,
        query_text=req.query,
        investigation_type=inv_type,
        entity_id=req.entity_id,
        scenarios_config=req.scenarios_config
    )
    return res


@router.get("/investigation/transaction/{transaction_id}")
def investigate_transaction(
    transaction_id: str = Path(..., description="ID of transaction to investigate"),
    db: Session = Depends(get_db)
):
    """
    Dedicated evidence-grounded investigation endpoint for a single transaction.
    Explains amount, failure reason, ML probability, candidate strategies evaluated, expected values, winning strategy, and autonomy action.
    """
    evidence_bundle = build_transaction_evidence(db, transaction_id)
    if "error" in evidence_bundle:
        raise HTTPException(status_code=404, detail=evidence_bundle["error"])

    query_text = f"Explain recovery decision and economics for transaction {transaction_id}"
    provider = GeminiLLMProvider()
    llm_res = provider.generate_explanation(
        query=query_text,
        system_prompt=SYSTEM_INVESTIGATION_PROMPT,
        evidence_bundle=evidence_bundle
    )

    return {
        "transaction_id": transaction_id,
        "investigation_type": InvestigationType.TRANSACTION_INVESTIGATION.value,
        "answer": llm_res["answer"],
        "confidence": llm_res.get("confidence", "HIGH"),
        "confidence_type": llm_res.get("confidence_type", "evidence_grounded"),
        "provider_used": llm_res.get("provider_used", "FallbackLLMProvider"),
        "evidence": evidence_bundle.get("evidence", []),
        "ground_truth_context": evidence_bundle.get("ground_truth_context", {})
    }


@router.get("/investigation/incident/{incident_id}")
def investigate_incident(
    incident_id: str = Path(..., description="ID of incident to investigate"),
    db: Session = Depends(get_db)
):
    """
    Dedicated evidence-grounded investigation endpoint for an operational incident.
    Explains affected entity, baseline metric, current metric, deviation, severity, root cause evidence, revenue at risk, and recommended actions.
    """
    evidence_bundle = build_incident_evidence(db, incident_id)
    if "error" in evidence_bundle:
        raise HTTPException(status_code=404, detail=evidence_bundle["error"])

    query_text = f"Explain root cause, severity, and financial impact for incident {incident_id}"
    provider = GeminiLLMProvider()
    llm_res = provider.generate_explanation(
        query=query_text,
        system_prompt=SYSTEM_INVESTIGATION_PROMPT,
        evidence_bundle=evidence_bundle
    )

    return {
        "incident_id": incident_id,
        "investigation_type": InvestigationType.INCIDENT_INVESTIGATION.value,
        "answer": llm_res["answer"],
        "confidence": llm_res.get("confidence", "HIGH"),
        "confidence_type": llm_res.get("confidence_type", "evidence_grounded"),
        "provider_used": llm_res.get("provider_used", "FallbackLLMProvider"),
        "evidence": evidence_bundle.get("evidence", []),
        "ground_truth_context": evidence_bundle.get("ground_truth_context", {})
    }
