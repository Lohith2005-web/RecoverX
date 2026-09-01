# RecoverX — System Architecture (Phase 1)

## Overview
RecoverX is a modular AI revenue recovery and payment intelligence platform. Phase 1 establishes the core backend foundation, relational database models, and realistic synthetic payment ecosystem simulator.

```text
┌─────────────────────────────────────────────────────────┐
│                    FastAPI App API                      │
│   GET /api/health           GET /api/transactions       │
│   GET /api/dashboard/metrics POST /api/simulator/scenario│
└────────────────────────────┬────────────────────────────┘
                             │
     ┌───────────────────────┴───────────────────────┐
     │                                               │
┌────▼────────────────────────┐    ┌─────────────────▼───────────┐
│     SQLAlchemy Database     │    │ Synthetic Payment Simulator │
│ (SQLite / PostgreSQL Ready) │    │  (Seed 42 / 50k dataset)    │
└─────────────────────────────┘    └─────────────────────────────┘
```

## Module Structure

* **`backend/app/db/`**:
  * `session.py`: Engine and SessionLocal configuration.
  * `models.py`: Declarative ORM models for Merchant, Customer, Gateway, Issuer, Transaction, Incident, RecoveryPrediction, RecoveryAction, AuditLog, and SimulationScenario.

* **`backend/app/simulator/`**:
  * `generator.py`: Deterministic dataset generator producing 50,000+ realistic correlated transactions.
  * `scenario_engine.py`: Dynamic failure scenario injector (Gateway B degradation).

* **`backend/app/api/`**:
  * `health.py`: Health check endpoint.
  * `transactions.py`: Transaction list, details, and count statistics.
  * `dashboard.py`: Unfabricated real financial metrics derived from the database.
  * `simulator.py`: Reset simulator and scenario injection APIs.

## Database Entities & Schemas
- **Merchants**: E-Commerce, SaaS, Retail Grocery, Travel.
- **Gateways**: Gateway A (Razorpay Prime), Gateway B (PayU Enterprise), Gateway C (Cashfree Switch).
- **Issuers**: HDFC, ICICI, SBI, Axis.
- **Transactions**: 50,000 records containing amount, timestamp, payment method, failure codes, customer success rate, latency, risk score, status, and ground truth recoverability tag.
- **Incidents**: Tracks detected failure rate anomalies and root causes.
