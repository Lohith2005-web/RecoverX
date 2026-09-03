# RecoverX — Evidence-Grounded AI Investigation Assistant Documentation

## Executive Overview
The **Evidence-Grounded AI Investigation Assistant** (Phase 5 Part B) provides a natural-language investigation interface grounded strictly in RecoverX backend metrics, deterministic root causes, and economic decision traces.

The AI assistant acts as an explanation layer over RecoverX ground truth, adhering to a strict safety grounding system prompt that prevents metric hallucination or unauthorized strategy selection.

---

## 1. Grounded Architecture

```
User Natural Language Question
              │
              ▼
Intent & Entity Classification
              │
              ▼
RecoverX Backend Data Retrieval
(DB, ML Model, Economic Engine, What-If Engine)
              │
              ▼
Structured Machine-Readable Evidence Bundle
              │
              ▼
LLM Provider Abstraction
(GeminiLLMProvider / FallbackLLMProvider)
              │
              ▼
Evidence-Grounded Explanation Response JSON
```

### Key Architectural Rules:
1. **Backend as Source of Truth**: All financial calculations, ML probabilities, root cause evidence, and scenario comparisons are performed exclusively by RecoverX backend engines. The LLM does **NOT** calculate numbers independently.
2. **Provider Abstraction**: Implements `LLMProvider` interface. If `GEMINI_API_KEY` or `GOOGLE_API_KEY` is present, it uses `GeminiLLMProvider`. If no key is present, it falls back seamlessly to `FallbackLLMProvider`.
3. **Fallback Phrasing**: The fallback provider uses grounded probabilistic phrasing ("The evidence indicates...", "RecoverX detected...", "The economic model selected...", "The model estimates...") and does **NOT** claim an AI model made the determination.
4. **Best-Effort Audit Logging**: Investigation queries are logged to `AIInvestigationLog` best-effort. A logging or database failure will **NEVER** block or fail an investigation API response.

---

## 2. Supported Investigation Types

1. **`TRANSACTION_INVESTIGATION`**: Explains recovery decision, ML probability $P_{ml}$, candidate strategies evaluated, expected values $EV$, selected strategy, confidence, and autonomy action for a specific payment transaction.
2. **`INCIDENT_INVESTIGATION`**: Explains affected entity, baseline metric, current metric, deviation percent, z-score, severity, root-cause evidence, and multi-tier revenue at risk for an operational incident.
3. **`WHAT_IF_EXPLANATION`**: Explains counterfactual scenario comparisons and economic trade-offs.
4. **`STRATEGY_EXPLANATION`**: Explains why specific recovery strategies were selected or rejected.
5. **`REVENUE_RISK_ANALYSIS`**: Explains gross, recoverable, and unrecoverable revenue at risk breakdown.
6. **`ROOT_CAUSE_EXPLANATION`**: Explains deterministic root cause reason codes and heuristic confidence.

---

## 3. Response Schema Example

```json
{
  "query": "Why did RecoverX choose gateway reroute for transaction txn_002963?",
  "investigation_type": "TRANSACTION_INVESTIGATION",
  "entity_id": "txn_002963",
  "answer": "The evidence indicates that transaction txn_002963 (amount: ₹2,705.90) failed due to GATEWAY_TIMEOUT. RecoverX estimated a base ML recoverability probability of 0.9585. The economic model selected strategy 'GATEWAY_REROUTE' yielding an expected net economic value of ₹2,653.37.",
  "confidence": "HIGH",
  "confidence_type": "evidence_grounded",
  "provider_used": "FallbackLLMProvider",
  "evidence": [
    {
      "type": "transaction_metric",
      "metric": "amount",
      "value": 2705.9,
      "source": "transactions.id=txn_002963"
    },
    {
      "type": "ml_prediction",
      "metric": "recoverability_probability",
      "value": 0.9585,
      "source": "ml_model.joblib"
    },
    {
      "type": "economic_decision",
      "strategy": "GATEWAY_REROUTE",
      "expected_economic_value": 2653.37,
      "source": "economic_recovery_decision_engine"
    }
  ]
}
```

---

## 4. API Endpoints

- `POST /api/investigation/query`: Submit natural language question or query payload.
- `GET /api/investigation/transaction/{transaction_id}`: Dedicated investigation endpoint for a payment transaction.
- `GET /api/investigation/incident/{incident_id}`: Dedicated investigation endpoint for an operational incident.
