# RecoverX — Autonomous Revenue Recovery & Payment Intelligence Platform

> **Razorpay AI Buildathon 2026 Submission**  
> Tagline: *Autonomous Revenue Recovery & Payment Intelligence*

RecoverX helps merchants identify payment-related revenue leakage and recover legitimate revenue automatically. It closes the loop from payment failure $\rightarrow$ AI analysis $\rightarrow$ strategy selection $\rightarrow$ confidence-gated execution $\rightarrow$ actual recovered revenue.

---

## Phase 1 Status (Foundation & Payment Ecosystem)

Phase 1 completes the core backend architecture, SQLite database foundation, and realistic synthetic payment ecosystem simulator:

* **FastAPI Backend**: Clean modular architecture.
* **Deterministic Payment Simulator**: Generates 50,000 realistic correlated transactions using seed `42`.
* **Gateway B Degradation Scenario Engine**: On-demand injection spiking failure rates and creating active incident records.
* **Financial Calculations**: Authentic revenue metrics derived directly from backend transaction state.

---

## Running the Backend

### Prerequisites
* Python 3.11+

### Setup & Run
```bash
# 1. Navigate to repository root
cd e:/RecoverX

# 2. Activate virtual environment
.\venv\Scripts\activate

# 3. Start FastAPI server
uvicorn backend.app.main:app --reload --port 8000
```

Access Swagger API docs at `http://127.0.0.1:8000/docs`.

---

## Running Unit Tests

```bash
.\venv\Scripts\pytest backend/tests
```

---

## API Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check endpoint |
| `GET` | `/api/transactions` | Paginated transaction list |
| `GET` | `/api/transactions/count` | Summary transaction status counts |
| `GET` | `/api/transactions/{id}` | Detailed transaction breakdown |
| `GET` | `/api/dashboard/metrics` | Dashboard aggregate metrics |
| `POST`| `/api/simulator/scenario` | Inject failure scenario (e.g., `GATEWAY_DEGRADATION`) |
| `POST`| `/api/simulator/reset` | Reset dataset back to baseline 50,000 transactions |
