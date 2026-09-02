import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.session import Base

def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    industry = Column(String, nullable=False, default="E-Commerce")

    transactions = relationship("Transaction", back_populates="merchant")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    historical_success_rate = Column(Float, nullable=False, default=0.85)
    country = Column(String, nullable=False, default="IN")

    transactions = relationship("Transaction", back_populates="customer")


class Gateway(Base):
    __tablename__ = "gateways"

    id = Column(String, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    baseline_failure_rate = Column(Float, nullable=False, default=0.02)
    status = Column(String, nullable=False, default="HEALTHY")

    transactions = relationship("Transaction", back_populates="gateway")


class Issuer(Base):
    __tablename__ = "issuers"

    id = Column(String, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    baseline_failure_rate = Column(Float, nullable=False, default=0.03)

    transactions = relationship("Transaction", back_populates="issuer")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.id"), index=True, nullable=False)
    merchant_id = Column(String, ForeignKey("merchants.id"), index=True, nullable=False)
    gateway_id = Column(String, ForeignKey("gateways.id"), index=True, nullable=False)
    issuer_id = Column(String, ForeignKey("issuers.id"), index=True, nullable=False)

    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="INR")
    timestamp = Column(DateTime, nullable=False, index=True)
    payment_method = Column(String, nullable=False, index=True) # UPI, CREDIT_CARD, DEBIT_CARD, NET_BANKING
    country = Column(String, nullable=False, default="IN")
    device_type = Column(String, nullable=False) # MOBILE_ANDROID, MOBILE_IOS, DESKTOP, WEB

    failure_code = Column(String, nullable=False, index=True, default="SUCCESS")
    failure_category = Column(String, nullable=False, index=True, default="NONE")
    retry_count = Column(Integer, nullable=False, default=0)
    customer_historical_success_rate = Column(Float, nullable=False)
    subscription_flag = Column(Boolean, nullable=False, default=False)
    checkout_session_id = Column(String, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    risk_score = Column(Float, nullable=False)

    status = Column(String, nullable=False, index=True, default="SUCCESS") # SUCCESS, FAILED, RECOVERED
    recovered_amount = Column(Float, nullable=False, default=0.0)
    scenario_tag = Column(String, nullable=False, default="NORMAL", index=True)

    # Ground truth label for ML model training (simulated realistic recovery potential)
    is_recoverable_ground_truth = Column(Boolean, nullable=False, default=False)

    # Relationships
    merchant = relationship("Merchant", back_populates="transactions")
    customer = relationship("Customer", back_populates="transactions")
    gateway = relationship("Gateway", back_populates="transactions")
    issuer = relationship("Issuer", back_populates="transactions")
    recovery_predictions = relationship("RecoveryPrediction", back_populates="transaction")
    recovery_actions = relationship("RecoveryAction", back_populates="transaction")
    recovery_decisions = relationship("RecoveryDecision", back_populates="transaction")
    recovery_executions = relationship("RecoveryExecution", back_populates="transaction")
    audit_events = relationship("AuditEvent", back_populates="transaction")



class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    incident_type = Column(String, nullable=False, default="GATEWAY_DEGRADATION") # GATEWAY_DEGRADATION, ISSUER_OUTAGE, PAYMENT_METHOD_INCIDENT, SYSTEM_TIMEOUT_SPIKE
    severity = Column(String, nullable=False, default="HIGH") # CRITICAL, HIGH, MEDIUM, LOW
    gateway_id = Column(String, ForeignKey("gateways.id"), nullable=True)
    issuer_id = Column(String, ForeignKey("issuers.id"), nullable=True)
    affected_payment_method = Column(String, nullable=True)
    anomaly_type = Column(String, nullable=False)
    baseline_rate = Column(Float, nullable=False)
    current_rate = Column(Float, nullable=False)
    affected_transactions = Column(Integer, nullable=False, default=0)
    revenue_at_risk = Column(Float, nullable=False, default=0.0) # Gross revenue at risk
    recoverable_revenue_at_risk = Column(Float, nullable=False, default=0.0)
    unrecoverable_revenue_at_risk = Column(Float, nullable=False, default=0.0)
    recovered_revenue = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.0)
    confidence_type = Column(String, nullable=False, default="heuristic")
    root_cause = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=True)
    evidence_json = Column(Text, nullable=False, default="{}")
    status = Column(String, nullable=False, default="ACTIVE") # ACTIVE, RESOLVED
    created_at = Column(DateTime, nullable=False, default=utc_now)
    resolved_at = Column(DateTime, nullable=True)

    timeline_events = relationship("IncidentTimelineEvent", back_populates="incident", cascade="all, delete-orphan")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(String, primary_key=True, index=True)
    metric = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False) # GATEWAY, ISSUER, PAYMENT_METHOD, SYSTEM
    entity_id = Column(String, nullable=True, index=True)
    current_value = Column(Float, nullable=False)
    baseline_value = Column(Float, nullable=False)
    deviation_percent = Column(Float, nullable=False)
    z_score = Column(Float, nullable=True)
    severity = Column(String, nullable=False) # CRITICAL, HIGH, MEDIUM, LOW
    evidence_json = Column(Text, nullable=False, default="{}")
    detected_at = Column(DateTime, nullable=False, default=utc_now)


class IncidentTimelineEvent(Base):
    __tablename__ = "incident_timeline_events"

    id = Column(String, primary_key=True, index=True)
    incident_id = Column(String, ForeignKey("incidents.id"), index=True, nullable=False)
    event_type = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)
    event_data = Column(Text, nullable=False, default="{}")
    timestamp = Column(DateTime, nullable=False, default=utc_now)

    incident = relationship("Incident", back_populates="timeline_events")



class RecoveryPrediction(Base):
    __tablename__ = "recovery_predictions"

    id = Column(String, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True, nullable=False)
    recoverability_score = Column(Float, nullable=False)
    expected_recovery_value = Column(Float, nullable=False)
    recommended_strategy = Column(String, nullable=False) # SMART_RETRY, GATEWAY_REROUTE, PAYMENT_METHOD_RECOVERY, CUSTOMER_RECOVERY, DO_NOTHING
    confidence_score = Column(Float, nullable=False)
    economic_expected_value = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    transaction = relationship("Transaction", back_populates="recovery_predictions")


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id = Column(String, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True, nullable=False)
    strategy = Column(String, nullable=False)
    executed_at = Column(DateTime, nullable=False, default=utc_now)
    status = Column(String, nullable=False, default="SUCCESS") # SUCCESS, FAILED
    outcome_status = Column(String, nullable=False, default="RECOVERED")
    actual_recovered_amount = Column(Float, nullable=False, default=0.0)
    recovery_cost = Column(Float, nullable=False, default=0.0)
    net_recovered_amount = Column(Float, nullable=False, default=0.0)

    transaction = relationship("Transaction", back_populates="recovery_actions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=utc_now, index=True)
    entity_type = Column(String, nullable=False) # TRANSACTION, INCIDENT, STRATEGY
    entity_id = Column(String, nullable=False)
    prediction = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    strategy = Column(String, nullable=False)
    autonomy_tier = Column(String, nullable=False) # AUTOMATIC, HUMAN_APPROVAL, BLOCKED
    action_status = Column(String, nullable=False)
    financial_impact = Column(Float, nullable=False, default=0.0)
    evidence_summary = Column(Text, nullable=False)


class SimulationScenario(Base):
    __tablename__ = "simulation_scenarios"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False) # GATEWAY_DEGRADATION, ISSUER_DEGRADATION, TIMEOUT_SPIKE
    target_gateway = Column(String, nullable=True)
    target_issuer = Column(String, nullable=True)
    failure_multiplier = Column(Float, nullable=False, default=1.0)
    is_active = Column(Boolean, nullable=False, default=False)
    injected_at = Column(DateTime, nullable=True)


class RecoveryDecision(Base):
    __tablename__ = "recovery_decisions"

    id = Column(String, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True, nullable=False)
    strategy = Column(String, nullable=False, index=True)
    recoverability_probability = Column(Float, nullable=False)
    strategy_success_probability = Column(Float, nullable=False)
    expected_recovery = Column(Float, nullable=False)
    recovery_cost = Column(Float, nullable=False)
    customer_friction_cost = Column(Float, nullable=False)
    risk_penalty = Column(Float, nullable=False)
    expected_economic_value = Column(Float, nullable=False)
    decision_confidence = Column(String, nullable=False)
    confidence_type = Column(String, nullable=False, default="heuristic")
    autonomy_action = Column(String, nullable=False)
    explanation_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=utc_now)

    transaction = relationship("Transaction", back_populates="recovery_decisions")
    execution = relationship("RecoveryExecution", back_populates="decision", uselist=False)


class RecoveryExecution(Base):
    __tablename__ = "recovery_executions"

    id = Column(String, primary_key=True, index=True)
    decision_id = Column(String, ForeignKey("recovery_decisions.id"), index=True, nullable=False, unique=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True, nullable=False)
    status = Column(String, nullable=False, default="EXECUTED")
    simulated_success = Column(Boolean, nullable=False, default=False)
    recovered_amount = Column(Float, nullable=False, default=0.0)
    recovery_cost = Column(Float, nullable=False, default=0.0)
    friction_cost = Column(Float, nullable=False, default=0.0)
    risk_penalty = Column(Float, nullable=False, default=0.0)
    net_recovered_amount = Column(Float, nullable=False, default=0.0)
    executed_at = Column(DateTime, nullable=False, default=utc_now)

    transaction = relationship("Transaction", back_populates="recovery_executions")
    decision = relationship("RecoveryDecision", back_populates="execution")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True, nullable=False)
    decision_id = Column(String, ForeignKey("recovery_decisions.id"), nullable=True)
    event_type = Column(String, nullable=False, index=True)
    event_data = Column(Text, nullable=False, default="{}")
    timestamp = Column(DateTime, nullable=False, default=utc_now, index=True)

    transaction = relationship("Transaction", back_populates="audit_events")

