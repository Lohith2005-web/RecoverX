# RecoverX — Economic Recovery Decision Engine Documentation

## Executive Overview
The **Economic Recovery Decision Engine** forms Phase 3 of the RecoverX platform.
While Phase 2 answers *"How likely is this failed payment to be recoverable?"* using XGBoost, Phase 3 answers *"What should RecoverX do about it, and is taking that action economically justified?"*

RecoverX rejects naive decision rules like `if probability > 0.5: retry`. Instead, it formulates recovery as a financial optimization problem using expected economic value, strategy-specific success probabilities, transaction amounts, direct recovery costs, customer friction costs, risk/compliance penalties, and autonomy confidence gates.

---

## 1. Decision Flow Architecture

```
                               ┌────────────────────────────────┐
                               │     Failed Payment Transaction │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │  Phase 2 Recoverability Model  │
                               │   (P_ml = XGBoost Prediction)  │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │      Strategy Evaluation       │
                               │  (Deterministic Evidence Adj.) │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │    Economic Value Formula      │
                               │  (Expected Net Revenue in Decimal)│
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │    Autonomy & Confidence Gate  │
                               │  (HIGH, MEDIUM, LOW Policy)    │
                               └───────────────┬────────────────┘
                                               │
            ┌──────────────────────────────────┼──────────────────────────────────┐
            ▼                                  ▼                                  ▼
 ┌────────────────────┐              ┌────────────────────┐             ┌────────────────────┐
 │    AUTO_ACTION     │              │     SIMULATE       │             │     DO_NOT_ACT     │
 │ (High Conf + EV>0) │              │(Med Conf / Approval│             │  (Low EV / Risk /  │
 └──────────┬─────────┘              └──────────┬─────────┘             │  Low Probability)  │
            │                                   │                       └────────────────────┘
            └─────────────────┬─────────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │     Simulated Execution      │
               │ (Duplicate Check + Audit Trail)│
               └──────────────┬─────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │    Measured Net Financial    │
               │        Outcome & EV          │
               └──────────────────────────────┘
```

---

## 2. Recovery Strategies

RecoverX evaluates five discrete strategies defined in `app.engine.constants.RecoveryStrategy`:

1. **`SMART_RETRY`**:
   - **Target**: Transient technical timeouts (`TECHNICAL_TIMEOUT`, `GATEWAY_TIMEOUT`, `NETWORK_ERROR`).
   - **Characteristics**: Low recovery cost, minimal customer friction.

2. **`GATEWAY_REROUTE`**:
   - **Target**: Degraded payment gateways (`gateway_status != HEALTHY`).
   - **Characteristics**: Switches traffic to alternative healthy gateways. High efficacy during gateway degradation incidents.

3. **`PAYMENT_METHOD_RECOVERY`**:
   - **Target**: Payment-method-specific errors (`INSUFFICIENT_FUNDS`, `CARD_EXPIRED`, `CARD_DECLINED`).
   - **Characteristics**: Prompts card update or alternative fund sources. Higher customer friction cost.

4. **`CUSTOMER_RECOVERY`**:
   - **Target**: Customer-side authentication issues (`AUTHENTICATION_FAILED`, `OTP_EXPIRED`, `INVALID_PIN`).
   - **Characteristics**: Direct user prompt/intervention required. Highest customer friction cost.

5. **`DO_NOT_ACT`**:
   - **Target**: Unrecoverable transactions, negative EV candidate outcomes, high compliance risk (`RISK_REJECTED`), or low recoverability probability.
   - **Policy Role**: Selected whenever no candidate strategy yields positive expected economic value ($EV > 0$).

---

## 3. Strategy-Specific Success Probability

Strategy-specific success probabilities ($P_{strategy\_success}$) are derived deterministically using the Phase 2 ML recoverability prediction ($P_{ml}$) adjusted boundedly in $[0.01, 0.99]$ based on empirical domain evidence.

### Evidence Adjustment Factors:

| Strategy | Condition / Feature Signal | Adjustment ($\Delta$) |
|---|---|---|
| **`SMART_RETRY`** | Technical timeout / network error | $+0.05$ |
| | Existing retry count ($N$) | $-0.15 \times N$ |
| | Degraded current gateway | $-0.25$ |
| | Non-transient failure code (`CARD_EXPIRED`, etc.) | $-0.40$ |
| **`GATEWAY_REROUTE`** | Current gateway degraded | $+0.25$ |
| | Current gateway healthy | $-0.10$ |
| | User/compliance failure code | $-0.50$ |
| **`PAYMENT_METHOD_RECOVERY`** | Fund / card error code | $+0.15$ |
| | Customer historical success rate $\ge 0.85$ | $+0.10$ |
| | Pure technical timeout | $-0.20$ |
| **`CUSTOMER_RECOVERY`** | Customer action error (OTP/PIN/Auth) | $+0.20$ |
| | Customer historical success rate $\ge 0.80$ | $+0.10$ |
| | Subscription transaction (unattended) | $-0.15$ |
| **Strict Compliance** | `RISK_REJECTED` or `risk_score` $> 0.35$ | $-0.80$ |

All adjustments are exposed transparently in the machine-readable `decision_trace`.

---

## 4. Economic Value Formula

RecoverX optimizes Expected Economic Value ($EV$) using Python's `Decimal` module for exact monetary precision:

$$\text{Expected Economic Value} = P_{strategy\_success} \times \text{transaction\_amount} - \text{recovery\_cost} - \text{customer\_friction\_cost} - \text{risk\_penalty}$$

### Financial Cost Components:
- **`transaction_amount`**: Gross monetary value of the failed transaction (INR).
- **`recovery_cost`**: Direct processing fee per strategy (`SMART_RETRY` = ₹10, `GATEWAY_REROUTE` = ₹15, `PAYMENT_METHOD_RECOVERY` = ₹8, `CUSTOMER_RECOVERY` = ₹5).
- **`customer_friction_cost`**: Cost scale for user annoyance/churn (`SMART_RETRY` = ₹2, `GATEWAY_REROUTE` = ₹5, `PAYMENT_METHOD_RECOVERY` = ₹15, `CUSTOMER_RECOVERY` = ₹40).
- **`risk_penalty`**: Compliance/chargeback penalty scale (`RISK_REJECTED` or high risk = ₹1000, standard = $\text{risk\_score} \times ₹50$).

---

## 5. Decision Confidence vs. ML Recoverability Probability

RecoverX explicitly separates two distinct metrics:

1. **`recoverability_probability`** ($P_{ml}$): XGBoost probability prediction of payment recoverability.
2. **`decision_confidence`**: Confidence in the selected **ACTION**, explicitly labeled as `"heuristic"`.

### Policy Threshold Matrix:

| Decision Confidence | ML Probability ($P_{ml}$) | Expected Economic Value ($EV$) | Policy Outcome |
|---|---|---|---|
| **`HIGH`** | $P_{ml} \ge 0.90$ | $EV > ₹0.00$ | **`AUTO_ACTION`** |
| **`MEDIUM`** | $P_{ml} \ge 0.70$ | $EV > ₹0.00$ | **`SIMULATE` / `HUMAN_APPROVAL`** |
| **`LOW`** | $P_{ml} < 0.70$ | $EV \le ₹0.00$ or Low Prob | **`DO_NOT_ACT`** |

---

## 6. Naive Single-Retry Baseline Comparison

RecoverX measures its financial lift against a **Naive Single Retry Baseline** evaluated on the **exact same transaction population**.

### Baseline Strategy:
- Retries every eligible failed payment once without ML or economic decision logic.
- Ignores customer friction and gateway health.

### Comparative Metrics:
- **Net Recovered Amount**: $\text{Gross Recovered} - \text{Recovery Costs} - \text{Friction Costs} - \text{Risk Penalties}$.
- **Actions Avoided**: Number of wasteful, negative-EV recovery attempts prevented by RecoverX.
- **Cost Reduction**: Total monetary savings from avoided low-probability retries.

---

## 7. Simulated Execution & Mutation Semantics

1. **/simulate (`POST /api/recovery/simulate/{transaction_id}`)**:
   - Performs dry-run calculation and simulated outcome prediction.
   - **Does NOT mutate** database state or transaction status.
2. **/execute (`POST /api/recovery/execute/{transaction_id}`)**:
   - Validates transaction has not already been recovered.
   - Prevents duplicate execution.
   - Updates transaction status to `RECOVERED` upon simulated success.
   - Records immutable `RecoveryExecution` and `AuditEvent` records.

---

## 8. Concrete Decision Examples

### Scenario A: Transient Technical Timeout (Healthy Gateway)
- **Transaction Amount**: ₹3,000.00 | **Failure**: `GATEWAY_TIMEOUT` | **Gateway**: HEALTHY
- **ML Probability ($P_{ml}$)**: 0.92
- **Strategy Selected**: `SMART_RETRY` ($P_{strategy\_success} = 0.97$)
- **EV Calculation**: $0.97 \times 3000 - 10 - 2 - 2.50 = ₹2,895.50$
- **Decision Confidence**: `HIGH` (`heuristic`) $\rightarrow$ **`AUTO_ACTION`**

### Scenario B: Degraded Gateway Timeout
- **Transaction Amount**: ₹5,000.00 | **Failure**: `GATEWAY_TIMEOUT` | **Gateway**: DEGRADED
- **ML Probability ($P_{ml}$)**: 0.75
- **Strategy Selected**: `GATEWAY_REROUTE` ($P_{strategy\_success} = 0.90$)
- **EV Calculation**: $0.90 \times 5000 - 15 - 5 - 2.50 = ₹4,477.50$
- **Decision Confidence**: `MEDIUM` (`heuristic`) $\rightarrow$ **`SIMULATE`**

### Scenario C: High Risk Compliance Failure
- **Transaction Amount**: ₹10,000.00 | **Failure**: `RISK_REJECTED` | **Risk Score**: 0.85
- **ML Probability ($P_{ml}$)**: 0.95 (High raw value, but compliance rule triggered)
- **Strategy Selected**: `DO_NOT_ACT`
- **EV Calculation**: -$₹1,000.00$ (Risk penalty)
- **Decision Confidence**: `LOW` (`heuristic`) $\rightarrow$ **`DO_NOT_ACT`**
