# RecoverX — What-If Recovery Simulation Documentation

## Executive Overview
The **What-If Recovery Simulation Engine** (Phase 5 Part A) allows merchant operations and finance teams to execute **pure counterfactual scenario analysis** on payment failure populations without mutating database state, execution logs, or baseline datasets.

It answers key business questions such as:
- *"What happens if Gateway B remains degraded?"*
- *"What happens if we reroute Gateway B failures to an alternative gateway?"*
- *"What happens if we raise the recoverability action threshold from 0.70 to 0.85?"*
- *"How much net revenue could RecoverX recover under each strategy?"*

---

## 1. Core Principles & Architecture

1. **Zero Database Mutation**: The What-If simulation engine is 100% read-only and counterfactual. It does NOT insert, update, or delete transaction records, recovery decisions, recovery executions, or incident timelines.
2. **Decimal Precision**: All monetary values (`gross_expected_recovery`, `expected_recovery_cost`, `expected_friction`, `expected_risk_penalty`, `expected_net_recovery`, `revenue_per_action`, `cost_per_successful_recovery`, `incremental_revenue_vs_baseline`, `incremental_net_recovery_vs_baseline`) are computed using Python `Decimal` precision.
3. **Reuse of Core Engines**: Reuses Phase 2 ML recoverability predictions, Phase 3 economic strategy engine, Phase 4 health indicators, and baseline comparison engines directly without duplicating business logic.
4. **Deterministic Backend Recommendations**: Multi-scenario comparisons rank scenarios strictly by backend-calculated `expected_net_recovery`, exposing risk penalty and expected attempts. An LLM is **NEVER** allowed to pick the recommended scenario.

---

## 2. Supported Scenario Semantics

- **`CURRENT_CONDITIONS`**: Evaluates recovery policy on the actual current payment system state.
- **`GATEWAY_DEGRADATION`**: Applies specified gateway health overrides (e.g. `{"gateway_b": "DEGRADED"}`) as counterfactual context.
- **`GATEWAY_REROUTE`**: Evaluates gateway rerouting counterfactual without bypassing Phase 3 economic decision calculations.
- **`THRESHOLD_ADJUSTMENT`**: Changes the recoverability/action threshold (e.g., `0.85`) while keeping the underlying transaction population and telemetry constant.

---

## 3. Metrics Calculated per Scenario

- `transactions_considered`: Total failed payment volume in observation window.
- `eligible_transactions`: Count of transactions meeting economic actionability ($P_{ml} \ge \text{threshold}$ and winning strategy $\ne$ `DO_NOT_ACT`).
- `predicted_recoverable_amount`: $\sum (\text{amount} \times P_{ml})$.
- `gross_expected_recovery`: $\sum (\text{amount} \times P_{success})$ for eligible attempts.
- `expected_recovery_cost`: Sum of transaction fees for recovery attempts.
- `expected_friction`: Sum of customer friction cost adjustments.
- `expected_risk_penalty`: Sum of compliance risk penalties.
- `expected_net_recovery`: $\text{Gross} - \text{Cost} - \text{Friction} - \text{Risk}$.
- `expected_attempts`: Count of recovery actions triggered.
- `expected_successes`: Sum of expected successful recoveries ($\sum P_{success}$).
- `expected_success_rate`: $\frac{\text{expected\_successes}}{\max(1, \text{expected\_attempts})}$.
- `revenue_per_action`: Net revenue generated per recovery action.
- `cost_per_successful_recovery`: Fee cost per successful recovery.
- `avoided_attempts`: Count of unpromising recovery attempts avoided ($\text{considered} - \text{attempts}$).
- `incremental_revenue_vs_baseline`: Gross revenue lift over Naive Single Retry baseline.
- `incremental_net_recovery_vs_baseline`: Net revenue lift over Naive Single Retry baseline.

---

## 4. API Specification

### `POST /api/simulation/what-if`
Executes a single counterfactual scenario simulation.

#### Request Body Example:
```json
{
  "name": "Gateway B Degraded + Reroute",
  "type": "GATEWAY_REROUTE",
  "gateway_status_overrides": {
    "gateway_b": "DEGRADED"
  },
  "recoverability_threshold": 0.70,
  "strategy_overrides": {
    "GATEWAY_TIMEOUT": "GATEWAY_REROUTE"
  },
  "include_baseline": true
}
```

---

### `POST /api/simulation/compare`
Evaluates and compares multiple scenarios in a single pass.

#### Request Body Example:
```json
{
  "scenarios": [
    { "name": "Current Conditions", "type": "CURRENT_CONDITIONS" },
    { "name": "Gateway B Degraded", "type": "GATEWAY_DEGRADATION", "gateway_status_overrides": { "gateway_b": "DEGRADED" } },
    { "name": "Gateway B Degraded + Reroute", "type": "GATEWAY_REROUTE", "gateway_status_overrides": { "gateway_b": "DEGRADED" } }
  ]
}
```
