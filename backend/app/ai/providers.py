import os
import json
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class LLMProvider(ABC):
    """Abstract Base Class for Evidence-Grounded LLM Providers."""
    
    @abstractmethod
    def generate_explanation(
        self,
        query: str,
        system_prompt: str,
        evidence_bundle: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generates an evidence-grounded natural language explanation."""
        pass


class FallbackLLMProvider(LLMProvider):
    """
    Deterministic Fallback Provider used when no LLM API keys are present.
    Produces evidence-grounded explanations without claiming AI model output.
    Uses precise phrasing: 'The evidence indicates...', 'RecoverX detected...', etc.
    """
    
    def generate_explanation(
        self,
        query: str,
        system_prompt: str,
        evidence_bundle: Dict[str, Any]
    ) -> Dict[str, Any]:
        inv_type = evidence_bundle.get("investigation_type", "")
        ground_truth = evidence_bundle.get("ground_truth_context", {})
        evidence_items = evidence_bundle.get("evidence", [])

        if inv_type == "TRANSACTION_INVESTIGATION":
            txn_id = ground_truth.get("id", "unknown")
            amount = ground_truth.get("amount", 0.0)
            p_ml = ground_truth.get("ml_recoverability_probability", 0.0)
            strat = ground_truth.get("selected_strategy", "DO_NOT_ACT")
            ev = ground_truth.get("expected_economic_value", 0.0)
            reason = ground_truth.get("explanation", {}).get("reason_codes", [])

            answer = (
                f"The evidence indicates that transaction {txn_id} (amount: ₹{amount:,.2f}) failed due to "
                f"{ground_truth.get('failure_code', 'payment failure')}. "
                f"RecoverX estimated a base ML recoverability probability of {p_ml:.4f}. "
                f"The economic model selected strategy '{strat}' yielding an expected net economic value of ₹{ev:,.2f}. "
                f"Supporting evidence factor codes: {', '.join(reason) if reason else 'standard policy'}."
            )

        elif inv_type == "INCIDENT_INVESTIGATION":
            inc_id = ground_truth.get("id", "unknown")
            entity = ground_truth.get("affected_entity", "system component")
            sev = ground_truth.get("severity", "MEDIUM")
            rc = ground_truth.get("root_cause", "Operational anomaly detected.")
            gross_risk = ground_truth.get("financial_impact", {}).get("gross_revenue_at_risk", 0.0)
            rec_risk = ground_truth.get("financial_impact", {}).get("recoverable_revenue_at_risk", 0.0)

            answer = (
                f"RecoverX detected operational incident '{inc_id}' affecting {entity} with severity '{sev}'. "
                f"The incident engine identifies root cause: '{rc}'. "
                f"The evidence indicates gross revenue at risk of ₹{gross_risk:,.2f}, of which ₹{rec_risk:,.2f} "
                f"is expected recoverable revenue based on Phase 2 ML predictions."
            )

        elif inv_type == "WHAT_IF_EXPLANATION":
            scenarios = ground_truth.get("scenarios", [])
            rec_scen = ground_truth.get("recommended_scenario", "Current Conditions")
            reason = ground_truth.get("recommendation_reason", "")

            answer = (
                f"The What-If scenario engine evaluated {len(scenarios)} counterfactual scenarios. "
                f"The evidence indicates that '{rec_scen}' is the optimal policy. "
                f"{reason}"
            )

        else:
            answer = (
                f"RecoverX analyzed query '{query}'. "
                f"The evidence indicates {len(evidence_items)} supporting data points from internal payment telemetry. "
                f"All metrics are calculated deterministically by backend engines."
            )

        return {
            "answer": answer,
            "confidence": "HIGH",
            "confidence_type": "evidence_grounded",
            "provider_used": "FallbackLLMProvider"
        }


class GeminiLLMProvider(LLMProvider):
    """
    Google Gemini LLM Provider abstraction.
    Falls back to FallbackLLMProvider if API key is missing or call fails.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.fallback = FallbackLLMProvider()

    def generate_explanation(
        self,
        query: str,
        system_prompt: str,
        evidence_bundle: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not self.api_key:
            return self.fallback.generate_explanation(query, system_prompt, evidence_bundle)

        try:
            # Construct API payload for Gemini API
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
            
            prompt_content = (
                f"{system_prompt}\n\n"
                f"USER QUERY: {query}\n\n"
                f"SUPPLIED RECOVERX EVIDENCE BUNDLE:\n"
                f"{json.dumps(evidence_bundle, indent=2)}\n\n"
                f"Instructions: Generate a concise, grounded explanation based strictly on the evidence bundle."
            )

            payload = {
                "contents": [
                    {
                        "parts": [{"text": prompt_content}]
                    }
                ]
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return {
                    "answer": text.strip(),
                    "confidence": "HIGH",
                    "confidence_type": "evidence_grounded",
                    "provider_used": "GeminiLLMProvider"
                }

        except Exception as e:
            # On any network failure or rate limit, fall back gracefully
            res = self.fallback.generate_explanation(query, system_prompt, evidence_bundle)
            res["provider_used"] = "FallbackLLMProvider (Gemini Call Failed)"
            return res
