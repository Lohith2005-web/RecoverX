# RecoverX — Synthetic Payment Simulator Documentation

## Overview
The RecoverX Synthetic Payment Simulator generates a realistic, correlated synthetic transaction dataset of approximately 50,000 transactions using a deterministic random seed (`42`).

## Design Principles & Correlations
1. **Deterministic Reproducibility**: Using seed 42 guarantees identical datasets across runs and demo environments.
2. **Correlated Attributes**:
   - **Gateway Latency & Baseline Failure**: Gateway A (1.8% baseline failure rate, ~180ms latency), Gateway B (2.2% baseline, ~220ms), Gateway C (3.5% baseline, ~280ms).
   - **Payment Methods & Amounts**:
     - `UPI`: 45% volume, average ~₹1,500.
     - `CREDIT_CARD`: 30% volume, average ~₹6,300.
     - `DEBIT_CARD`: 15% volume, average ~₹3,200.
     - `NET_BANKING`: 10% volume, average ~₹15,000.
   - **Customer Historical Success Rate**: Customers have intrinsic success rates (beta distribution). Customer history directly correlates with recovery probability.
   - **Failure Categories**:
     - `TECHNICAL_TIMEOUT` (`GATEWAY_TIMEOUT`): High recoverability.
     - `SYSTEM_DEGRADATION` (`GATEWAY_DEGRADATION`): High recoverability via reroute.
     - `USER_ERROR` (`INSUFFICIENT_FUNDS`, `CARD_EXPIRED`): Medium recoverability.
     - `COMPLIANCE_RISK` (`RISK_REJECTED`): Low recoverability.

## Failure Scenarios

### Scenario 1 — Gateway B Degradation
* **Mechanism**: Spikes failure rate of Gateway B from ~2.2% to ~14.8% by marking recent successful Gateway B transactions as `SYSTEM_DEGRADATION`.
* **Impact**: Spikes `revenue_at_risk`, increases latency by 450%, and automatically logs an active `Incident` record.
* **API Trigger**: `POST /api/simulator/scenario` with `{"scenario_type": "GATEWAY_DEGRADATION", "target_gateway": "gateway_b"}`.
