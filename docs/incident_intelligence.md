# RecoverX — Incident Intelligence & Anomaly Detection Documentation

## Executive Overview
**Incident Intelligence & Anomaly Detection** forms Phase 4 of the RecoverX platform.
While Phase 2 predicts payment recoverability ($P_{ml}$) and Phase 3 evaluates strategy-level expected economic value ($EV$), Phase 4 answers:

> *"Something changed in the payment ecosystem — what changed, where did it happen, how serious is it, what revenue is at risk, and why did it happen?"*

Phase 4 uses explainable, deterministic statistical methods (rolling baselines, percentage deviations, z-score supporting evidence) to detect operational anomalies, group them into unified incidents, calculate multi-tier revenue at risk in `Decimal`, perform deterministic root-cause reasoning, and provide degraded gateway context to the Phase 3 economic decision engine without hardcoding strategy selection.

---

## 1. Statistical Anomaly Detection Methodology

RecoverX monitors payment metrics across four operational dimensions:
1. **Gateways** (`GATEWAY_FAILURE_RATE`, `GATEWAY_TIMEOUT_RATE`)
2. **Issuers** (`ISSUER_FAILURE_RATE`)
3. **Payment Methods** (`PAYMENT_METHOD_FAILURE_RATE`)
4. **System Latency** (`LATENCY_SPIKE`)

### Historical Baseline vs. Current Observation Window
- **Historical Baseline Window**: Historical window (7 days) excluding the active observation window and excluding active injected scenario transactions (`scenario_tag == 'NORMAL'`).
- **Baseline Contamination Prevention**: Transactions belonging to active injected incidents are strictly filtered out from the historical baseline calculation.
- **Minimum Sample Size**: Requires $N \ge 40$ transactions in the baseline and $N_{failures} \ge 5$ affected failures to prevent small-sample random fluctuations from triggering false positives.

### Anomaly Signal Formulas:
1. **Percentage Deviation** (Primary Business Signal):
   $$\text{deviation\_percent} = \frac{\text{current\_value} - \text{baseline\_value}}{\max(0.0001, \text{baseline\_value})} \times 100$$
2. **Z-Score** (Supporting Statistical Evidence):
   $$z = \frac{\text{current\_value} - \mu_{baseline}}{\sigma_{baseline}}$$
   *(Calculated when $\sigma_{baseline} > 0$ as supporting evidence).*

---

## 2. Severity Classification Rules

Severity is assigned using transparent, deterministic deviation rules:

| Severity Level | Deviation Threshold | Absolute Failure Rate Increase | Operational Significance |
|---|---|---|---|
| **`CRITICAL`** | $\ge +300.0\%$ | $\ge +10.0\%$ absolute | Major gateway outage / severe system disruption |
| **`HIGH`** | $\ge +150.0\%$ | $\ge +5.0\%$ absolute | Significant entity degradation |
| **`MEDIUM`** | $\ge +100.0\%$ | $\ge +3.0\%$ absolute | Moderate failure rate spike |
| **`LOW`** | $\ge +50.0\%$ | $< +3.0\%$ absolute | Minor operational drift |

---

## 3. Incident Grouping & Idempotency

### Incident Grouping
Multiple related anomalies across dimensions are grouped into a single operational `Incident` object keyed by entity (e.g., `GATEWAY:gateway_b`).

### Idempotency Guarantee
Repeated detection calls (`POST /api/incidents/detect`) on unchanged data update existing `ACTIVE` incidents in place (updating current failure rates, affected transaction counts, revenue at risk, evidence payload, and timeline) rather than creating duplicate active incident rows.

---

## 4. Deterministic Root-Cause Reasoning Engine

Root-cause analysis is 100% deterministic and explainable (no LLM or black-box ML).
Root-cause confidence is explicitly labeled as **`confidence_type = "heuristic"`**.

### Root Cause Decision Tree Examples:

```
[Anomaly Detected on Gateway B]
         │
         ├──► Failure codes dominated by GATEWAY_TIMEOUT / SYSTEM_DEGRADATION?
         │         │
         │         ├──► Yes: Other gateways operating at baseline (~2%)?
         │         │         │
         │         │         └──► Yes: Root Cause = "GATEWAY_DEGRADATION"
         │         │                   Reason Codes = ["GATEWAY_B_FAILURE_SPIKE", "TECHNICAL_TIMEOUT_DOMINATED", "OTHER_GATEWAYS_NORMAL"]
         │         │                   Confidence = 0.95 (heuristic)
```

---

## 5. Multi-Tier Revenue at Risk (Decimal Precision)

For every incident, RecoverX calculates a 4-tier revenue impact breakdown using `Decimal` arithmetic:

1. **`gross_revenue_at_risk`**:
   $$\text{Gross} = \sum \text{transaction\_amount} \quad \text{for all failed transactions in incident window}$$
2. **`expected_recoverable_revenue_at_risk`**:
   $$\text{Expected Recoverable} = \sum (\text{transaction\_amount} \times P_{ml}) \quad \text{using Phase 2 ML recoverability prediction}$$
3. **`expected_unrecoverable_revenue`**:
   $$\text{Expected Unrecoverable} = \text{Gross} - \text{Expected Recoverable}$$
4. **`actual_recovered_revenue`**:
   $$\text{Actual Recovered} = \sum \text{recovered\_amount} \quad \text{for executed recovery actions}$$

---

## 6. Integration with Phase 3 Economic Decision Engine

Phase 4 **does NOT force or hardcode recovery strategies**. Strategy selection remains 100% an economic decision.

### Integration Flow:
1. Phase 4 detects an active incident on Gateway B and sets `gateway.status = "DEGRADED"`.
2. When Phase 3 evaluates failed transactions on Gateway B, Phase 3 reads `gateway.status == "DEGRADED"`.
3. Phase 3's probability model applies a $+0.25$ adjustment to $P_{strategy\_success}$ for `GATEWAY_REROUTE`.
4. Phase 3 calculates expected economic value ($EV$) across all strategies (`SMART_RETRY`, `GATEWAY_REROUTE`, `PAYMENT_METHOD_RECOVERY`, `CUSTOMER_RECOVERY`).
5. `GATEWAY_REROUTE` yields the highest positive $EV$ and wins naturally through **economic decision logic**.

---

## 7. Machine-Readable Incident Timeline & Evidence

Every incident maintains an immutable audit trail of timeline events (`IncidentTimelineEvent`):
- `INCIDENT_STARTED`: Initial anomaly detection timestamp and metrics.
- `ROOT_CAUSE_IDENTIFIED`: Summary, reason codes, and heuristic confidence score.
- `RECOVERY_RECOMMENDATIONS_GENERATED`: Expected recoverable revenue and recommended operational actions.
- `RECOVERY_ACTIONS_TAKEN`: Log of simulated or automated recovery executions.
- `INCIDENT_RESOLVED`: Event logged when metric returns to baseline.

---

## 8. Limitations

1. **Synthetic Scenario Context**: Baseline calculations operate on the synthetic payment dataset. Real-world deployments require tuning baseline windows for seasonal traffic cycles (e.g. Black Friday volume spikes).
2. **Deterministic Rules**: Root-cause analysis relies on explicit rule paths. New failure codes require registering corresponding reason code mappings in `root_cause_engine.py`.
