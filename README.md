# RecoverX — Autonomous Revenue Recovery & Payment Intelligence Platform

> **Razorpay AI Buildathon 2026 Submission**  
> *Tagline: Autonomous Revenue Recovery & Payment Intelligence Platform*

RecoverX is a production-grade, end-to-end autonomous revenue recovery platform designed to eliminate payment-related revenue leakage. It closes the loop from payment failure $\rightarrow$ ML recoverability prediction $\rightarrow$ economic strategy decisioning $\rightarrow$ anomaly & incident detection $\rightarrow$ counterfactual what-if simulation $\rightarrow$ evidence-grounded AI investigation.

---

## 1. Problem Statement & Mission

Every year, digital merchants lose up to 5–10% of gross transaction volume to payment failures. Traditional recovery tools rely on rigid, naive retry rules (e.g., retrying every failed transaction 3 times), which lead to:
* **High Customer Friction**: Spamming retries triggers card issuer blocklists and damages customer relationships.
* **Negative Economic Value**: Executing costly retries or gateway reroutes on unrecoverable payments wastes operational margin.
* **Infrastructure Blind Spots**: Siloed retries fail to detect underlying gateway degradations or upstream bank latency spikes.

**RecoverX solves this by reformulating revenue recovery as a financial optimization problem**, combining machine learning probabilities with exact `Decimal` monetary optimization, autonomous confidence gates, and evidence-grounded AI investigation.

---

## 2. Complete Phase 1–6 Platform Architecture

```
                                    +----------------------------------+
                                    | RecoverX React 19 Command Center |
                                    +----------------------------------+
                                                     |
                                                     v (FastAPI REST APIs)
+----------------------------------------------------------------------------------------------------+
|                                      RECOVERX BACKEND CORE                                         |
|                                                                                                    |
|  +---------------------+   +---------------------+   +---------------------+   +-----------------+ |
|  |   Phase 1: Payment  |   |    Phase 2: XGBoost  |   |  Phase 3: Economic  |   |  Phase 4: Anomaly| |
|  |   Ecosystem & DB    |   | ML Predictor Engine |   |  Decision Engine    |   |  & Incident Engine| |
|  | (50k Txns, Seed 42) |   |  (P_recoverable)    |   |  (Decimal Net EV)   |   | (4-Tier Impact) | |
|  +---------------------+   +---------------------+   +---------------------+   +-----------------+ |
|                                       |                         |                       |          |
|                                       v                         v                       v          |
|  +----------------------------------------------------------------------------------------------+ |
|  | Phase 5A: What-If Counterfactual Simulator  | Phase 5B: Evidence-Grounded AI Assistant        | |
|  +----------------------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
```

### Phase 1: Synthetic Ecosystem Simulator
* Generates 50,000 realistic, correlated payment transactions using a deterministic random seed (`42`).
* Multi-dimensional schema capturing customers, merchants, gateways (`gtw_a`, `gtw_b`, `gtw_c`), issuing banks (`isr_hdfc`, `isr_icici`, etc.), payment methods (`UPI`, `CREDIT_CARD`, `NET_BANKING`), failure categories, latency, and risk scores.

### Phase 2: ML Recoverability Model
* Binary classification pipeline using an **XGBoost Classifier** trained on pre-action features strictly barring data leakage.
* Outputs pure recoverability probability estimates ($P_{\text{recoverable}} \in [0.0, 1.0]$).

### Phase 3: Economic Decision Engine & Autonomy Gates
* Rejects naive retry rules; formulates recovery using exact `Decimal` net economic value ($EV$):
  $$EV = P_{\text{strategy\_success}} \times \text{Amount} - \text{Direct Cost} - \text{Friction Cost} - \text{Risk Penalty}$$
* Evaluates 5 discrete recovery strategies: `DO_NOT_ACT`, `SMART_RETRY_IMMEDIATE`, `SMART_RETRY_SCHEDULED`, `GATEWAY_REROUTE`, `CUSTOMER_NUDGE`.
* Autonomous execution confidence gates: `AUTO_EXECUTE` ($\ge 0.90$), `APPROVAL_REQUIRED` ($0.70 - 0.89$), `DO_NOT_ACT` ($< 0.70$).

### Phase 4: Incident Intelligence & Anomaly Detection
* Monitors rolling 7-day baselines vs. 15-minute observation windows to detect payment degradation spikes.
* Computes 4-tier revenue impact breakdown: *Gross Revenue at Risk*, *Expected Recoverable Revenue*, *Expected Unrecoverable Revenue*, and *Actual Recovered Revenue*.
* Deterministic root-cause heuristics matching degraded gateways and error codes.

### Phase 5A: What-If Counterfactual Simulation Engine
* Allows merchant finance teams to simulate counterfactual recovery strategies across transaction populations without mutating live database state.

### Phase 5B: Evidence-Grounded AI Investigation Assistant
* Provides natural language investigation interface grounded strictly in backend engine evidence bundles.
* Implements provider abstraction: uses **Google Gemini 1.5 Flash** when `GEMINI_API_KEY` is provided, and gracefully falls back to deterministic `FallbackLLMProvider` if unconfigured.

### Phase 6: Autonomous Command Center UI
* Built with React 19, TypeScript, Vite, Tailwind CSS, Recharts, and Lucide icons.
* Responsive dark-mode dashboard featuring KPI cards, Incident Spotlight, Strategy Matrix, Gateway Health Grid, What-If Simulator, and AI Assistant.

---

## 3. Quickstart & Clean Setup

### System Prerequisites
* **Python**: 3.11 or higher
* **Node.js**: v18.0.0 or higher
* **npm**: v9.0.0 or higher

---

### Backend Setup

```bash
# 1. Navigate to repository root
cd RecoverX

# 2. Create and activate virtual environment
# Windows (PowerShell):
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS:
python3 -m venv venv
source venv/bin/activate

# 3. Install Python dependencies
pip install -r backend/requirements.txt

# 4. Start FastAPI Server
uvicorn backend.app.main:app --reload --port 8000
```
> The API will be available at `http://127.0.0.1:8000`.
> Interactive Swagger API documentation: `http://127.0.0.1:8000/docs`.

---

### Frontend Setup

Open a second terminal window:

```bash
# 1. Navigate to frontend directory
cd RecoverX/frontend

# 2. Install Node dependencies
npm install

# 3. Start Vite development server
npm run dev
```
> Access the Command Center in your browser at `http://localhost:5173`.

---

## 4. Environment Variables

Create an optional `.env` file in the root directory (or set environment variables in your shell):

```env
# Optional: Google Gemini API key for live LLM responses
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Database connection string (defaults to sqlite:///./recoverx.db)
DATABASE_URL=sqlite:///./recoverx.db

# Optional: Frontend API base URL (defaults to http://127.0.0.1:8000/api)
VITE_API_URL=http://127.0.0.1:8000/api
```

---

## 5. Verification & Testing

### Running Backend Unit Tests (45 Tests)
```bash
# From repository root (with venv activated)
pytest backend/tests
```

### Running Frontend Unit Tests (3 Tests)
```bash
# From frontend directory
cd frontend
npm run test
```

### Validating Production Build
```bash
cd frontend
npm run build
```

---

## 6. Judge Demo Walkthrough

1. **Launch Backend & Frontend**: Start both servers following the quickstart instructions above.
2. **Open Command Center (`http://localhost:5173`)**:
   - The app automatically initializes with the canonical **Gateway B Degradation Incident** spotlight active.
   - Observe live calculated KPI metrics (*Gross Revenue At Risk*, *Oracle Recoverable*, *Actual Recovered*).
3. **Interactive Scenario Controls**:
   - Use the **"Reset Dataset"** button in the header to return the ecosystem to the baseline 50,000 transaction state.
   - Use the **"Inject Incident"** button to trigger a live failure rate spike on Gateway B and watch the Incident Spotlight activate dynamically.
4. **Investigate Operational Incident**:
   - Click **"Investigate Incident"** on the spotlight banner to view affected transaction lists, timeline events, and root cause evidence.
5. **Run What-If Counterfactual Simulation**:
   - Click **"Run What-If Simulation"** to open the scenario matrix. Adjust thresholds and run comparative strategy models.
6. **Single Transaction Investigation**:
   - Navigate to **"Transaction Investigation"**. The page loads deterministic failed transaction `txn_000040` (or any selected candidate) showcasing full economic decision traces and strategy calculations.
7. **Ask AI Investigation Assistant**:
   - Click any suggested question (e.g. *"Why did RecoverX choose gateway reroute?"*) in the AI assistant panel to receive an evidence-grounded natural language explanation.

---

## 7. Baseline Comparison & Financial Claims

RecoverX measures its performance against a **Naive Single-Retry Baseline** (retrying every failed payment once indiscriminately).

### Honest Outperformance Findings:
* **Attempt Minimization**: Avoids wasteful retries on low-probability/high-risk transactions, reducing customer friction and gateway fees.
* **Higher Net Economic Return**: Maximizes net recovered revenue per action by factoring in friction costs and risk penalties.
* **Capital Efficiency**: Achieves lower cost per successful recovery compared to indiscriminate retries.

*Note on Transparency*: RecoverX does NOT claim to exceed naive retries in absolute gross revenue under all theoretical conditions, because naive retries unconditionally attempt 100% of failures regardless of margin erosion or compliance risk. RecoverX optimizes **Net Economic Value**.

---

## 8. Synthetic Data & System Disclaimer

* All transaction, merchant, customer, and gateway data displayed in this application are synthetically generated using deterministic seeds (`42`).
* The ML model and economic algorithms demonstrate authentic engineering architecture for AI revenue recovery and do not claim to represent live internal Razorpay production systems.
