# RecoverX — Machine Learning Pipeline (Recoverability Model)

## 1. Executive Overview
The RecoverX ML Pipeline predicts the **recoverability probability** ($P(\text{Recoverable})$) of failed payment transactions. It provides pure probability estimates to be consumed by downstream economic decision systems without incorporating business rules or execution logic into the model itself.

---

## 2. ML Problem Formulation
* **Task**: Binary Classification.
* **Target Label**: `is_recoverable`
  * `1`: The failed transaction is recoverable when an appropriate recovery action is applied.
  * `0`: The failed transaction is unrecoverable.
* **Model Output**: `recoverability_probability` $\in [0.0, 1.0]$.

---

## 3. Pre-Action Information Principle & Feature Set
The model is strictly constrained to features known **before** any recovery action is taken.

### Numerical Features
* `amount`: Transaction monetary value (INR).
* `retry_count`: Prior retry attempts (0 to 3+).
* `customer_historical_success_rate`: Customer's historical success ratio (0.0 to 1.0).
* `latency_ms`: Checkout API latency in milliseconds.
* `risk_score`: Fraud/risk assessment score (0.0 to 1.0).
* `hour_of_day`: Hour extracted from transaction timestamp (0 to 23).
* `day_of_week`: Day of week extracted from timestamp (0 to 6).

### Categorical Features
* `payment_method`: `UPI`, `CREDIT_CARD`, `DEBIT_CARD`, `NET_BANKING`.
* `gateway_id`: Primary gateway routing code (`gtw_a`, `gtw_b`, `gtw_c`).
* `issuer_id`: Issuing bank code (`isr_hdfc`, `isr_icici`, `isr_sbi`, `isr_axis`).
* `failure_category`: `TECHNICAL_TIMEOUT`, `USER_ERROR`, `COMPLIANCE_RISK`, `SYSTEM_DEGRADATION`.
* `failure_code`: `GATEWAY_TIMEOUT`, `INSUFFICIENT_FUNDS`, `CARD_EXPIRED`, `AUTHENTICATION_FAILED`, `RISK_REJECTED`, `GATEWAY_DEGRADATION`.
* `subscription_flag`: Boolean recurring billing indicator.
* `device_type`: `MOBILE_ANDROID`, `MOBILE_IOS`, `DESKTOP`, `WEB`.

---

## 4. Data Leakage Prevention Strategy
To prevent data leakage, post-action and outcome attributes are explicitly barred from feature extraction.

### Strictly Forbidden Fields
* `status` (`SUCCESS`, `FAILED`, `RECOVERED`)
* `recovered_amount`
* `is_recoverable_ground_truth` (Target label)
* `outcome_status`
* `actual_recovered_amount`
* `recovery_cost`
* `net_recovered_amount`

Validation is enforced programmatically via `validate_no_data_leakage(df)` in `backend/app/ml/feature_engineering.py`.

---

## 5. Pipeline Architecture & Data Split
* **Dataset**: 50,000 synthetic transactions generated with seed `42` (filtered to failed transactions).
* **Train / Test Split**: 80% Training ($N_{train}$), 20% Test ($N_{test}$), stratified by target label `y`.
* **Preprocessing**: Scikit-Learn `ColumnTransformer`:
  * Categorical features transformed via `OneHotEncoder(handle_unknown='ignore', sparse_output=False)`.
  * Numerical features scaled via `StandardScaler()`.
  * Preprocessor is fitted **exclusively on the training dataset** (`X_train`) to prevent data leakage.
* **Classifier**: XGBoost Classifier (`n_estimators=100`, `max_depth=5`, `learning_rate=0.1`, `random_state=42`).

---

## 6. Model Persistence & Inference API
* **Model Serialization**: `joblib.dump()` saves the complete fitted Pipeline to `backend/app/ml/models/recoverability_model.joblib`.
* **Metrics Storage**: JSON evaluation report stored at `backend/app/ml/models/evaluation_results.json`.
* **Inference Endpoint**: `predict_recoverability(features_dict)` accepts pre-action transaction details and returns:
```json
{
  "recoverability_probability": 0.875,
  "model_version": "1.0.0",
  "prediction_timestamp": "2026-09-01T12:00:00Z"
}
```

---

## 7. Retraining CLI
To retrain the model on current database state:
```bash
python backend/app/ml/train.py
```
Or via HTTP POST request to `/api/evaluation/train`.
