import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.session import Base, get_db
from app.simulator.generator import seed_database

TEST_DB_FILE = "./test_api_recoverx.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)

    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = TestingSessionLocal()
    seed_database(db, num_transactions=2000, seed=42)
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

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_transactions_endpoints():
    # Test transactions count
    resp_count = client.get("/api/transactions/count")
    assert resp_count.status_code == 200
    count_data = resp_count.json()
    assert "total_transactions" in count_data
    assert count_data["total_transactions"] == 2000

    # Test transactions list
    resp_list = client.get("/api/transactions?limit=10")
    assert resp_list.status_code == 200
    list_data = resp_list.json()
    assert list_data["limit"] == 10
    assert len(list_data["transactions"]) == 10

    # Test single transaction detail
    first_id = list_data["transactions"][0]["id"]
    resp_detail = client.get(f"/api/transactions/{first_id}")
    assert resp_detail.status_code == 200
    detail_data = resp_detail.json()
    assert detail_data["id"] == first_id
    assert "customer" in detail_data
    assert "gateway" in detail_data

def test_dashboard_metrics_endpoint():
    response = client.get("/api/dashboard/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_transactions"] == 2000
    assert data["total_transaction_value"] > 0
    assert data["revenue_at_risk"] > 0
    assert "gateway_performance" in data
    assert len(data["gateway_performance"]) == 3

def test_simulator_scenario_and_reset():
    # Inject Gateway Degradation scenario
    resp_inj = client.post("/api/simulator/scenario", json={"scenario_type": "GATEWAY_DEGRADATION", "target_gateway": "gateway_b"})
    assert resp_inj.status_code == 200
    inj_data = resp_inj.json()
    assert inj_data["status"] == "success"
    assert inj_data["scenario"] == "GATEWAY_DEGRADATION"

    # Check dashboard reflects active incident
    resp_dash = client.get("/api/dashboard/metrics")
    dash_data = resp_dash.json()
    assert dash_data["active_incidents_count"] > 0

    # Reset simulator
    resp_reset = client.post("/api/simulator/reset")
    assert resp_reset.status_code == 200
    reset_data = resp_reset.json()
    assert reset_data["status"] == "success"
