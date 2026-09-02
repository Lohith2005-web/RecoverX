import os
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.db.models import Transaction, Gateway, Customer, RecoveryDecision, RecoveryExecution, AuditEvent
from app.simulator.generator import seed_database
from app.engine.constants import (
    RecoveryStrategy,
    DecisionConfidence,
    AutonomyAction
)
from app.engine.economic_model import calculate_strategy_probability, calculate_economic_value
from app.engine.strategy_selector import evaluate_recovery_decision
from app.engine.confidence_gate import determine_confidence_and_autonomy
from app.engine.execution import execute_recovery_decision, simulate_execution_outcome
from app.engine.baseline_engine import evaluate_naive_baseline_and_recoverx

TEST_DB_FILE = "./test_recovery_engine.db"
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

# 1. Smart retry selected for appropriate technical failures
def test_smart_retry_selected_for_technical_failure():
    txn_data = {
        "failure_category": "TECHNICAL_TIMEOUT",
        "failure_code": "GATEWAY_TIMEOUT",
        "gateway_status": "HEALTHY",
        "retry_count": 0,
        "customer_historical_success_rate": 0.90,
        "risk_score": 0.05
    }
    decision = evaluate_recovery_decision(0.85, 3000.0, txn_data)
    assert decision["strategy"] == RecoveryStrategy.SMART_RETRY.value
    assert "TRANSIENT_TECHNICAL_FAILURE" in decision["explanation"]["reason_codes"] or "SMART_RETRY_OPTIMAL" in decision["explanation"]["reason_codes"]

# 2. Gateway reroute selected when gateway degradation supports it
def test_gateway_reroute_selected_when_degraded():
    txn_data = {
        "failure_category": "TECHNICAL_TIMEOUT",
        "failure_code": "GATEWAY_TIMEOUT",
        "gateway_status": "DEGRADED",
        "retry_count": 0,
        "customer_historical_success_rate": 0.90,
        "risk_score": 0.05
    }
    decision = evaluate_recovery_decision(0.80, 5000.0, txn_data)
    assert decision["strategy"] == RecoveryStrategy.GATEWAY_REROUTE.value
    assert "CURRENT_GATEWAY_DEGRADED" in decision["explanation"]["reason_codes"]

# 3. Payment method recovery selected for appropriate payment failures
def test_payment_method_recovery_selected():
    txn_data = {
        "failure_category": "USER_ERROR",
        "failure_code": "INSUFFICIENT_FUNDS",
        "gateway_status": "HEALTHY",
        "retry_count": 0,
        "customer_historical_success_rate": 0.92,
        "risk_score": 0.02
    }
    decision = evaluate_recovery_decision(0.85, 4000.0, txn_data)
    assert decision["strategy"] == RecoveryStrategy.PAYMENT_METHOD_RECOVERY.value
    assert "PAYMENT_METHOD_ISSUE" in decision["explanation"]["reason_codes"]

# 4. Customer recovery selected when customer action is appropriate
def test_customer_recovery_selected():
    txn_data = {
        "failure_category": "USER_ERROR",
        "failure_code": "AUTHENTICATION_FAILED",
        "gateway_status": "HEALTHY",
        "retry_count": 0,
        "customer_historical_success_rate": 0.88,
        "subscription_flag": False,
        "risk_score": 0.03
    }
    decision = evaluate_recovery_decision(0.85, 6000.0, txn_data)
    assert decision["strategy"] == RecoveryStrategy.CUSTOMER_RECOVERY.value
    assert "CUSTOMER_ACTION_REQUIRED" in decision["explanation"]["reason_codes"]

# 5. Do-not-act for low recoverability
def test_do_not_act_for_low_recoverability():
    txn_data = {
        "failure_category": "USER_ERROR",
        "failure_code": "CARD_DECLINED",
        "gateway_status": "HEALTHY",
        "retry_count": 2,
        "customer_historical_success_rate": 0.40,
        "risk_score": 0.20
    }
    decision = evaluate_recovery_decision(0.05, 500.0, txn_data)
    assert decision["strategy"] == RecoveryStrategy.DO_NOT_ACT.value
    assert decision["autonomy_action"] == AutonomyAction.DO_NOT_ACT.value

# 6. Do-not-act for negative economic value
def test_do_not_act_for_negative_economic_value():
    txn_data = {
        "failure_category": "TECHNICAL_TIMEOUT",
        "failure_code": "GATEWAY_TIMEOUT",
        "gateway_status": "HEALTHY",
        "retry_count": 2,
        "customer_historical_success_rate": 0.50,
        "risk_score": 0.10
    }
    # Amount is ₹10 (less than recovery costs)
    decision = evaluate_recovery_decision(0.40, 10.0, txn_data)
    assert decision["strategy"] == RecoveryStrategy.DO_NOT_ACT.value
    assert decision["expected_economic_value"] <= 0.0

# 7. High confidence produces AUTO_ACTION
def test_high_confidence_produces_auto_action():
    conf, autonomy, trace = determine_confidence_and_autonomy(
        0.95,
        RecoveryStrategy.SMART_RETRY,
        Decimal("450.00"),
        {"failure_code": "GATEWAY_TIMEOUT", "risk_score": 0.02}
    )
    assert conf == DecisionConfidence.HIGH
    assert autonomy == AutonomyAction.AUTO_ACTION

# 8. Medium confidence produces SIMULATE / HUMAN_APPROVAL
def test_medium_confidence_produces_simulate():
    conf, autonomy, trace = determine_confidence_and_autonomy(
        0.75,
        RecoveryStrategy.GATEWAY_REROUTE,
        Decimal("300.00"),
        {"failure_code": "GATEWAY_TIMEOUT", "risk_score": 0.02}
    )
    assert conf == DecisionConfidence.MEDIUM
    assert autonomy == AutonomyAction.SIMULATE

# 9. Low confidence produces DO_NOT_ACT
def test_low_confidence_produces_do_not_act():
    conf, autonomy, trace = determine_confidence_and_autonomy(
        0.50,
        RecoveryStrategy.SMART_RETRY,
        Decimal("50.00"),
        {"failure_code": "GATEWAY_TIMEOUT", "risk_score": 0.02}
    )
    assert conf == DecisionConfidence.LOW
    assert autonomy == AutonomyAction.DO_NOT_ACT

# 10. Risk/compliance cases are not automatically recovered
def test_risk_reject_blocks_automatic_recovery():
    txn_data = {
        "failure_category": "COMPLIANCE_RISK",
        "failure_code": "RISK_REJECTED",
        "gateway_status": "HEALTHY",
        "risk_score": 0.85
    }
    decision = evaluate_recovery_decision(0.95, 10000.0, txn_data)
    assert decision["strategy"] == RecoveryStrategy.DO_NOT_ACT.value
    assert decision["autonomy_action"] == AutonomyAction.DO_NOT_ACT.value
    assert "RISK_COMPLIANCE_REJECTED" in decision["explanation"]["reason_codes"]

# 11. Duplicate execution is prevented & 12/13 execution state changes
def test_simulated_execution_and_duplicate_prevention():
    db = TestingSessionLocal()
    
    # Pick a failed transaction
    txn = db.query(Transaction).filter(Transaction.status == "FAILED", Transaction.failure_code != "RISK_REJECTED").first()
    assert txn is not None
    txn_id = txn.id

    # Execute recovery with seed=42
    res = execute_recovery_decision(db, transaction_id=txn_id, seed=42)
    assert res["is_simulated"] is True
    assert res["transaction_id"] == txn_id
    assert "execution_id" in res

    # Verify DB transaction record updated if simulated_success
    db.refresh(txn)
    if res["simulated_success"]:
        assert txn.status == "RECOVERED"
        assert txn.recovered_amount > 0.0
    else:
        assert txn.recovered_amount == 0.0

    # Attempt duplicate execution -> Must fail with ValueError
    with pytest.raises(ValueError, match="already been recovered|Duplicate execution prevented"):
        execute_recovery_decision(db, transaction_id=txn_id, seed=42)

    db.close()

# 14. Economic value calculation correctness with Decimal
def test_economic_value_calculation_accuracy():
    econ = calculate_economic_value(
        RecoveryStrategy.SMART_RETRY,
        0.80,
        2500.0,
        {"failure_code": "GATEWAY_TIMEOUT", "risk_score": 0.04}
    )
    assert econ["expected_recovery"] == Decimal("2000.00")
    assert econ["recovery_cost"] == Decimal("10.00")
    assert econ["customer_friction_cost"] == Decimal("2.00")
    assert econ["risk_penalty"] == Decimal("2.00")
    assert econ["expected_economic_value"] == Decimal("1986.00")

# 15. Naive baseline calculation & 16. Same population metrics
def test_baseline_and_population_comparison():
    db = TestingSessionLocal()

    metrics = evaluate_naive_baseline_and_recoverx(db)
    
    assert "baseline_naive_retry" in metrics
    assert "recoverx_engine" in metrics
    assert "comparison" in metrics
    
    b_metrics = metrics["baseline_naive_retry"]
    rx_metrics = metrics["recoverx_engine"]

    # Same population check
    assert metrics["dataset_summary"]["total_failed_transactions"] > 0
    assert b_metrics["eligible_failed_transactions"] > 0
    assert rx_metrics["eligible_failed_transactions"] == metrics["dataset_summary"]["total_failed_transactions"]
    
    # Net financial & actions avoided metrics present
    assert "net_recovered_amount" in b_metrics
    assert "net_recovered_amount" in rx_metrics
    assert "actions_avoided" in metrics["comparison"]

    db.close()

# API Endpoints Integration Tests
def test_recovery_api_endpoints():
    # 1. Opportunities endpoint
    resp_opp = client.get("/api/recovery/opportunities?limit=5")
    assert resp_opp.status_code == 200
    opp_data = resp_opp.json()
    assert "opportunities" in opp_data
    assert len(opp_data["opportunities"]) > 0

    first_txn_id = opp_data["opportunities"][0]["transaction_id"]

    # 2. GET Decision endpoint
    resp_dec = client.get(f"/api/recovery/decision/{first_txn_id}")
    assert resp_dec.status_code == 200
    dec_data = resp_dec.json()
    assert "decision" in dec_data
    assert "strategy" in dec_data["decision"]
    assert "decision_trace" in dec_data["decision"]

    # 3. POST Decision endpoint
    resp_post_dec = client.post(f"/api/recovery/decision/{first_txn_id}")
    assert resp_post_dec.status_code == 200
    post_dec_data = resp_post_dec.json()
    assert post_dec_data["status"] == "success"
    assert "decision_id" in post_dec_data

    # 4. POST Simulate endpoint (Must NOT mutate DB state)
    resp_sim = client.post(f"/api/recovery/simulate/{first_txn_id}?seed=42")
    assert resp_sim.status_code == 200
    sim_data = resp_sim.json()
    assert sim_data["mutation_occurred"] is False
    assert sim_data["is_simulated"] is True

    # 5. Metrics endpoint
    resp_met = client.get("/api/recovery/metrics")
    assert resp_met.status_code == 200
    met_data = resp_met.json()
    assert "total_decisions_generated" in met_data

    # 6. Baseline endpoint
    resp_base = client.get("/api/recovery/baseline")
    assert resp_base.status_code == 200
    base_data = resp_base.json()
    assert "baseline_naive_retry" in base_data
    assert "recoverx_engine" in base_data
