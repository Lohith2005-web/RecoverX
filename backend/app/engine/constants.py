from enum import Enum
from decimal import Decimal

class RecoveryStrategy(str, Enum):
    SMART_RETRY = "SMART_RETRY"
    GATEWAY_REROUTE = "GATEWAY_REROUTE"
    PAYMENT_METHOD_RECOVERY = "PAYMENT_METHOD_RECOVERY"
    CUSTOMER_RECOVERY = "CUSTOMER_RECOVERY"
    DO_NOT_ACT = "DO_NOT_ACT"

class DecisionConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ConfidenceType(str, Enum):
    HEURISTIC = "heuristic"

class AutonomyAction(str, Enum):
    AUTO_ACTION = "AUTO_ACTION"
    SIMULATE = "SIMULATE"
    DO_NOT_ACT = "DO_NOT_ACT"

# Cost constants (using Decimal for precise financial calculations in INR)
STRATEGY_BASE_COSTS = {
    RecoveryStrategy.SMART_RETRY: Decimal("10.00"),
    RecoveryStrategy.GATEWAY_REROUTE: Decimal("15.00"),
    RecoveryStrategy.PAYMENT_METHOD_RECOVERY: Decimal("8.00"),
    RecoveryStrategy.CUSTOMER_RECOVERY: Decimal("5.00"),
    RecoveryStrategy.DO_NOT_ACT: Decimal("0.00"),
}

STRATEGY_FRICTION_COSTS = {
    RecoveryStrategy.SMART_RETRY: Decimal("2.00"),
    RecoveryStrategy.GATEWAY_REROUTE: Decimal("5.00"),
    RecoveryStrategy.PAYMENT_METHOD_RECOVERY: Decimal("15.00"),
    RecoveryStrategy.CUSTOMER_RECOVERY: Decimal("40.00"),
    RecoveryStrategy.DO_NOT_ACT: Decimal("0.00"),
}

# Policy Thresholds
HIGH_CONFIDENCE_PROBABILITY_THRESHOLD = 0.90
MEDIUM_CONFIDENCE_PROBABILITY_THRESHOLD = 0.70
HIGH_RISK_SCORE_THRESHOLD = 0.35
