import uuid
import json
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models import AIInvestigationLog, utc_now
from app.ai.constants import InvestigationType
from app.ai.providers import GeminiLLMProvider, FallbackLLMProvider
from app.ai.evidence_builder import (
    build_transaction_evidence,
    build_incident_evidence,
    build_what_if_evidence
)
from app.ai.prompts import SYSTEM_INVESTIGATION_PROMPT

logger = logging.getLogger("recoverx.ai")

def route_and_investigate_query(
    db: Session,
    query_text: str,
    investigation_type: Optional[InvestigationType] = None,
    entity_id: Optional[str] = None,
    scenarios_config: Optional[list] = None
) -> Dict[str, Any]:
    """
    Main investigation entrypoint.
    Retrieves ground-truth evidence, invokes LLM provider abstraction, and logs audit record best-effort.
    """
    q_lower = query_text.lower().strip()

    # Automatic intent classification if not specified
    if not investigation_type:
        if "txn_" in q_lower or "transaction" in q_lower:
            investigation_type = InvestigationType.TRANSACTION_INVESTIGATION
            # Extract txn ID if present
            words = query_text.split()
            for w in words:
                if w.startswith("txn_"):
                    entity_id = w.strip(",.?!")
                    break
        elif "inc_" in q_lower or "incident" in q_lower or "outage" in q_lower or "degradation" in q_lower:
            investigation_type = InvestigationType.INCIDENT_INVESTIGATION
            words = query_text.split()
            for w in words:
                if w.startswith("inc_"):
                    entity_id = w.strip(",.?!")
                    break
        elif "what if" in q_lower or "remains degraded" in q_lower or "reroute" in q_lower:
            investigation_type = InvestigationType.WHAT_IF_EXPLANATION
        elif "root cause" in q_lower or "why" in q_lower:
            investigation_type = InvestigationType.ROOT_CAUSE_EXPLANATION
        elif "revenue at risk" in q_lower or "impact" in q_lower:
            investigation_type = InvestigationType.REVENUE_RISK_ANALYSIS
        else:
            investigation_type = InvestigationType.STRATEGY_EXPLANATION

    # Retrieve Evidence Bundle based on investigation type
    if investigation_type == InvestigationType.TRANSACTION_INVESTIGATION and entity_id:
        evidence_bundle = build_transaction_evidence(db, entity_id)
    elif investigation_type == InvestigationType.INCIDENT_INVESTIGATION and entity_id:
        evidence_bundle = build_incident_evidence(db, entity_id)
    elif investigation_type in [InvestigationType.WHAT_IF_EXPLANATION, InvestigationType.REVENUE_RISK_ANALYSIS]:
        evidence_bundle = build_what_if_evidence(db, scenarios_config=scenarios_config)
    else:
        # Default or fallback evidence
        if entity_id and entity_id.startswith("txn_"):
            evidence_bundle = build_transaction_evidence(db, entity_id)
        elif entity_id and entity_id.startswith("inc_"):
            evidence_bundle = build_incident_evidence(db, entity_id)
        else:
            evidence_bundle = build_what_if_evidence(db, scenarios_config=scenarios_config)

    # Invoke Provider Abstraction (Gemini if key configured, otherwise Fallback)
    provider = GeminiLLMProvider()
    llm_res = provider.generate_explanation(
        query=query_text,
        system_prompt=SYSTEM_INVESTIGATION_PROMPT,
        evidence_bundle=evidence_bundle
    )

    response_payload = {
        "query": query_text,
        "investigation_type": investigation_type.value if isinstance(investigation_type, InvestigationType) else str(investigation_type),
        "entity_id": entity_id,
        "answer": llm_res["answer"],
        "confidence": llm_res.get("confidence", "HIGH"),
        "confidence_type": llm_res.get("confidence_type", "evidence_grounded"),
        "provider_used": llm_res.get("provider_used", "FallbackLLMProvider"),
        "evidence": evidence_bundle.get("evidence", []),
        "ground_truth_context": evidence_bundle.get("ground_truth_context", {})
    }

    # Best-Effort Logging (Failure tolerance: logging failure NEVER crashes request)
    try:
        log_entry = AIInvestigationLog(
            id=f"ailog_{uuid.uuid4().hex[:10]}",
            query_text=query_text,
            investigation_type=response_payload["investigation_type"],
            entity_id=entity_id,
            answer=response_payload["answer"],
            confidence=response_payload["confidence"],
            confidence_type=response_payload["confidence_type"],
            evidence_json=json.dumps(response_payload["evidence"]),
            created_at=utc_now()
        )
        db.add(log_entry)
        db.commit()
    except Exception as ex:
        logger.warning(f"Best-effort AI investigation log failed gracefully: {ex}")
        db.rollback()

    return response_payload
