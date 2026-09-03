import os
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.db.models import Transaction, Gateway, Incident, RecoveryExecution, RecoveryDecision
from app.simulator.generator import seed_database
from app.simulation.constants import ScenarioType
from app.simulation.what_if_engine import run_what_if_simulation
from app.simulation.scenario_comparator import compare_recovery_scenarios

TEST_DB_FILE = "./test_simulation_whatif_recoverx.db"
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

# 1. Single What-If simulation execution
def test_single_what_if_simulation():
    db = TestingSessionLocal()
    res = run_what_if_simulation(
        db,
        scenario_name="Current Conditions",
        scenario_type=ScenarioType.CURRENT_CONDITIONS,
        recoverability_threshold=0.70
    )
    assert res["scenario_name"] == "Current Conditions"
    assert "metrics" in res
    m = res["metrics"]
    assert m["transactions_considered"] > 0
    assert m["gross_expected_recovery"] >= 0.0
    assert m["expected_net_recovery"] >= 0.0
    db.close()

# 2. ZERO DATABASE MUTATION GUARANTEE
def test_zero_database_mutation_guarantee():
    db = TestingSessionLocal()
    
    txn_count_before = db.query(Transaction).count()
    inc_count_before = db.query(Incident).count()
    dec_count_before = db.query(RecoveryDecision).count()
    exec_count_before = db.query(RecoveryExecution).count()

    # Run complex scenario simulation with overrides
    res = run_what_if_simulation(
        db,
        scenario_name="Gateway B Counterfactual",
        gateway_status_overrides={"gateway_b": "DEGRADED"},
        recoverability_threshold=0.85,
        strategy_overrides={"GATEWAY_TIMEOUT": "GATEWAY_REROUTE"}
    )

    txn_count_after = db.query(Transaction).count()
    inc_count_after = db.query(Incident).count()
    dec_count_after = db.query(RecoveryDecision).count()
    exec_count_after = db.query(RecoveryExecution).count()

    assert txn_count_before == txn_count_after
    assert inc_count_before == inc_count_after
    assert dec_count_before == dec_count_after
    assert exec_count_before == exec_count_after
    db.close()

# 3. Threshold adjustment effect
def test_threshold_adjustment_effect():
    db = TestingSessionLocal()
    res_normal = run_what_if_simulation(db, recoverability_threshold=0.70)
    res_strict = run_what_if_simulation(db, recoverability_threshold=0.90)

    # Stricter threshold should yield fewer or equal eligible attempts
    assert res_strict["metrics"]["expected_attempts"] <= res_normal["metrics"]["expected_attempts"]
    db.close()

# 4. Multi-scenario comparative evaluation
def test_multi_scenario_comparison():
    db = TestingSessionLocal()
    comp = compare_recovery_scenarios(db)
    assert "scenarios" in comp
    assert len(comp["scenarios"]) == 4
    assert "recommended_scenario" in comp
    assert "recommendation_reason" in comp
    assert len(comp["evidence"]) > 0
    db.close()

# 5. REST API /api/simulation/what-if and /api/simulation/compare
def test_simulation_api_endpoints():
    # POST /api/simulation/what-if
    resp_whatif = client.post("/api/simulation/what-if", json={
        "name": "Gateway B Reroute Test",
        "type": "GATEWAY_REROUTE",
        "gateway_status_overrides": {"gateway_b": "DEGRADED"},
        "recoverability_threshold": 0.70
    })
    assert resp_whatif.status_code == 200
    data_whatif = resp_whatif.json()
    assert data_whatif["scenario_name"] == "Gateway B Reroute Test"

    # POST /api/simulation/compare
    resp_comp = client.post("/api/simulation/compare", json={
        "observation_hours": 72
    })
    assert resp_comp.status_code == 200
    data_comp = resp_comp.json()
    assert len(data_comp["scenarios"]) == 4
    assert data_comp["recommended_scenario"] is not None
