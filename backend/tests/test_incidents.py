import os
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.db.models import Transaction, Gateway, Issuer, Incident, Anomaly, IncidentTimelineEvent
from app.simulator.generator import seed_database
from app.simulator.scenario_engine import inject_gateway_degradation, reset_simulator
from app.incidents.constants import IncidentSeverity, IncidentStatus
from app.incidents.anomaly_detector import detect_payment_anomalies, compute_percentage_deviation, compute_z_score
from app.incidents.root_cause_engine import analyze_root_cause
from app.incidents.incident_manager import process_and_group_incidents, compute_incident_revenue_at_risk

TEST_DB_FILE = "./test_incidents_recoverx.db"
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

# 1. Normal traffic does NOT create false incidents
def test_normal_traffic_no_false_incidents():
    db = TestingSessionLocal()
    # On pristine baseline, failure rates are normal (~2%) -> no anomalies triggered
    anoms = detect_payment_anomalies(db, observation_hours=72)
    assert len(anoms) == 0
    db.close()

# 2. Gateway B degradation detection & 3. Timeout spike detection
def test_gateway_b_degradation_detection():
    db = TestingSessionLocal()
    
    # Inject Gateway B degradation scenario
    res = inject_gateway_degradation(db, gateway_code="gateway_b")
    assert res["status"] == "success"

    anoms = detect_payment_anomalies(db, observation_hours=72)
    assert len(anoms) > 0
    
    gtw_b_anom = next((a for a in anoms if a["entity_id"] == "gateway_b"), None)
    assert gtw_b_anom is not None
    assert gtw_b_anom["deviation_percent"] > 100.0
    assert gtw_b_anom["severity"] in ["HIGH", "CRITICAL"]

    db.close()

# 4. Severity calculation correctness
def test_percentage_deviation_and_severity_calculation():
    dev = compute_percentage_deviation(0.12, 0.02)  # 6x baseline = +500%
    assert dev == 500.0
    
    z = compute_z_score(0.12, 0.02, 0.01)
    assert z == 10.0

# 5. Root Cause Reasoning
def test_root_cause_reasoning():
    primary = {
        "metric": "GATEWAY_TIMEOUT_RATE",
        "entity_type": "GATEWAY",
        "entity_id": "gateway_b",
        "entity_name": "PayU Enterprise",
        "deviation_percent": 385.5
    }
    rc = analyze_root_cause(primary, [primary], [])
    assert rc["incident_type"] == "GATEWAY_DEGRADATION"
    assert "GATEWAY_B_FAILURE_SPIKE" in rc["reason_codes"]
    assert "OTHER_GATEWAYS_NORMAL" in rc["reason_codes"]
    assert rc["confidence_type"] == "heuristic"

# 6. Revenue at Risk Decimal calculation
def test_revenue_at_risk_decimal_precision():
    db = TestingSessionLocal()
    rev = compute_incident_revenue_at_risk(db, observation_hours=72)
    assert isinstance(rev["gross"], Decimal)
    assert isinstance(rev["recoverable"], Decimal)
    assert isinstance(rev["unrecoverable"], Decimal)
    assert rev["gross"] >= Decimal("0.00")
    db.close()

# 7. Idempotency test: Repeated detection on unchanged data
def test_idempotent_incident_detection():
    db = TestingSessionLocal()
    inc1 = process_and_group_incidents(db, observation_hours=72)
    assert len(inc1) > 0

    active_count_before = db.query(Incident).filter(Incident.status == "ACTIVE").count()

    # Second call should update existing active incident without duplicate rows
    inc2 = process_and_group_incidents(db, observation_hours=72)
    active_count_after = db.query(Incident).filter(Incident.status == "ACTIVE").count()

    assert active_count_before == active_count_after
    db.close()

# 8. Phase 3 Integration: Gateway status set to DEGRADED & Phase 3 independently evaluates EV
def test_phase3_integration_degraded_gateway_context():
    db = TestingSessionLocal()
    gtw_b = db.query(Gateway).filter(Gateway.code == "gateway_b").first()
    assert gtw_b.status == "DEGRADED"

    # Fetch a degraded Gateway B technical failure transaction with good customer history
    txn = db.query(Transaction).filter(
        Transaction.gateway_id == gtw_b.id,
        Transaction.status == "FAILED",
        Transaction.scenario_tag == "GATEWAY_B_DEGRADATION",
        Transaction.customer_historical_success_rate >= 0.85
    ).first()
    assert txn is not None

    # Call Phase 3 GET decision endpoint -> must return decision where GATEWAY_REROUTE is evaluated independently
    resp = client.get(f"/api/recovery/decision/{txn.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gateway_status"] == "DEGRADED"
    assert "decision" in data
    assert data["decision"]["strategy"] == "GATEWAY_REROUTE"
    assert "CURRENT_GATEWAY_DEGRADED" in data["decision"]["explanation"]["reason_codes"]
    
    db.close()

# 9. API Endpoints Integration Tests
def test_incidents_api_endpoints():
    # List incidents
    resp_inc = client.get("/api/incidents")
    assert resp_inc.status_code == 200
    inc_data = resp_inc.json()
    assert len(inc_data["incidents"]) > 0

    first_inc_id = inc_data["incidents"][0]["id"]

    # Incident detail
    resp_detail = client.get(f"/api/incidents/{first_inc_id}")
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["id"] == first_inc_id
    assert "financial_impact" in detail

    # Timeline events
    resp_tl = client.get(f"/api/incidents/{first_inc_id}/timeline")
    assert resp_tl.status_code == 200
    tl = resp_tl.json()
    assert len(tl["timeline_events"]) >= 3

    # Impact breakdown
    resp_imp = client.get(f"/api/incidents/{first_inc_id}/impact")
    assert resp_imp.status_code == 200
    imp = resp_imp.json()
    assert "gross_revenue_at_risk" in imp
    assert "expected_recoverable_revenue_at_risk" in imp

    # Detect endpoint
    resp_det = client.post("/api/incidents/detect")
    assert resp_det.status_code == 200
    det = resp_det.json()
    assert det["status"] == "success"
