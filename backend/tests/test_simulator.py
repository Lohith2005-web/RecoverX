import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db.models import Transaction, Gateway, Incident
from app.simulator.generator import seed_database
from app.simulator.scenario_engine import inject_gateway_degradation, reset_simulator

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_deterministic_seed_generator(db_session):
    """
    Verify seed generator creates realistic correlated transactions deterministically.
    """
    res = seed_database(db_session, num_transactions=2000, seed=42)
    assert res["status"] == "success"
    assert res["transactions_generated"] == 2000

    total_txns = db_session.query(Transaction).count()
    assert total_txns == 2000

    # Verify correlations: FAILED transactions should have correlated failure categories
    failed_txns = db_session.query(Transaction).filter(Transaction.status == "FAILED").all()
    assert len(failed_txns) > 0

    for f in failed_txns:
        assert f.failure_category in ["TECHNICAL_TIMEOUT", "USER_ERROR", "COMPLIANCE_RISK", "SYSTEM_DEGRADATION"]
        assert f.failure_code in ["GATEWAY_TIMEOUT", "INSUFFICIENT_FUNDS", "CARD_EXPIRED", "AUTHENTICATION_FAILED", "RISK_REJECTED", "GATEWAY_DEGRADATION"]

def test_gateway_b_degradation_scenario(db_session):
    """
    Verify Gateway B degradation scenario spikes failure rate and creates incident.
    """
    seed_database(db_session, num_transactions=2000, seed=42)
    
    gtw_b = db_session.query(Gateway).filter(Gateway.code == "gateway_b").first()
    assert gtw_b.status == "HEALTHY"

    inj_res = inject_gateway_degradation(db_session, gateway_code="gateway_b")
    assert inj_res["status"] == "success"
    assert inj_res["target_gateway"] == "gateway_b"
    assert inj_res["affected_transactions"] > 0
    assert inj_res["new_failure_rate"] > gtw_b.baseline_failure_rate

    # Check updated gateway status
    db_session.refresh(gtw_b)
    assert gtw_b.status == "DEGRADED"

    # Check active incident created
    incident = db_session.query(Incident).filter(Incident.gateway_id == gtw_b.id).first()
    assert incident is not None
    assert incident.anomaly_type == "GATEWAY_DEGRADATION"
    assert incident.status == "ACTIVE"
    assert incident.revenue_at_risk > 0
