import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.db.models import Transaction, Incident, Gateway
from app.simulator.generator import seed_database
from app.simulator.scenario_engine import inject_gateway_degradation
from app.incidents.incident_manager import process_and_group_incidents
from app.ai.constants import InvestigationType
from app.ai.providers import FallbackLLMProvider, GeminiLLMProvider
from app.ai.evidence_builder import build_transaction_evidence, build_incident_evidence, build_what_if_evidence
from app.ai.investigation_router import route_and_investigate_query

TEST_DB_FILE = "./test_ai_investigation_recoverx.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except PermissionError:
            pass

    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    seed_database(db, num_transactions=500, seed=42)
    inject_gateway_degradation(db, gateway_code="gateway_b")
    process_and_group_incidents(db, observation_hours=72)
    db.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except PermissionError:
            pass

client = TestClient(app)

# 1. Fallback Provider Phrasing Verification
def test_fallback_provider_phrasing():
    fallback = FallbackLLMProvider()
    evidence_bundle = {
        "investigation_type": "TRANSACTION_INVESTIGATION",
        "ground_truth_context": {
            "id": "txn_0001",
            "amount": 1500.0,
            "ml_recoverability_probability": 0.85,
            "selected_strategy": "SMART_RETRY",
            "expected_economic_value": 1250.0,
            "explanation": {"reason_codes": ["TRANSIENT_FAILURE"]}
        },
        "evidence": []
    }
    res = fallback.generate_explanation("Why smart retry?", "prompt", evidence_bundle)
    answer = res["answer"]
    assert "The evidence indicates" in answer
    assert "RecoverX estimated" in answer
    assert "SMART_RETRY" in answer
    assert res["confidence_type"] == "evidence_grounded"

# 2. Transaction Evidence Construction
def test_transaction_evidence_builder():
    db = TestingSessionLocal()
    txn = db.query(Transaction).first()
    assert txn is not None

    ev = build_transaction_evidence(db, txn.id)
    assert ev["investigation_type"] == InvestigationType.TRANSACTION_INVESTIGATION.value
    assert ev["entity_id"] == txn.id
    assert len(ev["evidence"]) >= 3
    assert ev["ground_truth_context"]["selected_strategy"] is not None
    db.close()

# 3. Incident Evidence Construction
def test_incident_evidence_builder():
    db = TestingSessionLocal()
    inc = db.query(Incident).first()
    assert inc is not None

    ev = build_incident_evidence(db, inc.id)
    assert ev["investigation_type"] == InvestigationType.INCIDENT_INVESTIGATION.value
    assert ev["entity_id"] == inc.id
    assert len(ev["evidence"]) >= 3
    assert ev["ground_truth_context"]["severity"] is not None
    db.close()

# 4. What-If Evidence Construction
def test_what_if_evidence_builder():
    db = TestingSessionLocal()
    ev = build_what_if_evidence(db)
    assert ev["investigation_type"] == InvestigationType.WHAT_IF_EXPLANATION.value
    assert "recommended_scenario" in ev["ground_truth_context"]
    assert len(ev["evidence"]) > 0
    db.close()

# 5. Natural Language Routing & Query Handler
def test_natural_language_query_routing():
    db = TestingSessionLocal()
    txn = db.query(Transaction).first()
    
    # Query specifying txn ID
    res1 = route_and_investigate_query(db, f"Why did RecoverX choose strategy for {txn.id}?")
    assert res1["investigation_type"] == InvestigationType.TRANSACTION_INVESTIGATION.value
    assert res1["answer"] is not None
    assert len(res1["evidence"]) > 0

    # What-if query
    res2 = route_and_investigate_query(db, "What happens if Gateway B remains degraded?")
    assert res2["investigation_type"] == InvestigationType.WHAT_IF_EXPLANATION.value
    assert res2["answer"] is not None

    db.close()

# 6. Unknown Transaction / Incident Error Handling
def test_unknown_entity_error_handling():
    resp_txn = client.get("/api/investigation/transaction/txn_nonexistent_999")
    assert resp_txn.status_code == 404

    resp_inc = client.get("/api/investigation/incident/inc_nonexistent_999")
    assert resp_inc.status_code == 404

# 7. REST API Integration Tests
def test_ai_investigation_api_endpoints():
    db = TestingSessionLocal()
    txn = db.query(Transaction).first()
    inc = db.query(Incident).first()
    db.close()

    # POST /api/investigation/query
    resp_q = client.post("/api/investigation/query", json={
        "query": "How much revenue is currently at risk?",
        "investigation_type": "REVENUE_RISK_ANALYSIS"
    })
    assert resp_q.status_code == 200
    data_q = resp_q.json()
    assert "answer" in data_q
    assert len(data_q["evidence"]) > 0

    # GET /api/investigation/transaction/{id}
    resp_t = client.get(f"/api/investigation/transaction/{txn.id}")
    assert resp_t.status_code == 200
    data_t = resp_t.json()
    assert data_t["transaction_id"] == txn.id

    # GET /api/investigation/incident/{id}
    resp_i = client.get(f"/api/investigation/incident/{inc.id}")
    assert resp_i.status_code == 200
    data_i = resp_i.json()
    assert data_i["incident_id"] == inc.id
