from enum import Enum

class AnomalyMetric(str, Enum):
    FAILURE_RATE = "FAILURE_RATE"
    GATEWAY_FAILURE_RATE = "GATEWAY_FAILURE_RATE"
    GATEWAY_TIMEOUT_RATE = "GATEWAY_TIMEOUT_RATE"
    ISSUER_FAILURE_RATE = "ISSUER_FAILURE_RATE"
    PAYMENT_METHOD_FAILURE_RATE = "PAYMENT_METHOD_FAILURE_RATE"
    VOLUME_DROP = "VOLUME_DROP"
    LATENCY_SPIKE = "LATENCY_SPIKE"

class IncidentType(str, Enum):
    GATEWAY_DEGRADATION = "GATEWAY_DEGRADATION"
    ISSUER_OUTAGE = "ISSUER_OUTAGE"
    PAYMENT_METHOD_INCIDENT = "PAYMENT_METHOD_INCIDENT"
    SYSTEM_TIMEOUT_SPIKE = "SYSTEM_TIMEOUT_SPIKE"

class IncidentSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class IncidentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    INVESTIGATING = "INVESTIGATING"

class TimelineEventType(str, Enum):
    INCIDENT_STARTED = "INCIDENT_STARTED"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    ROOT_CAUSE_IDENTIFIED = "ROOT_CAUSE_IDENTIFIED"
    RECOVERY_RECOMMENDATIONS_GENERATED = "RECOVERY_RECOMMENDATIONS_GENERATED"
    RECOVERY_ACTIONS_TAKEN = "RECOVERY_ACTIONS_TAKEN"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"

# Statistical Baseline and Window Settings
MIN_SAMPLE_SIZE = 40                      # Minimum total transactions required in baseline & observation
MIN_AFFECTED_COUNT = 5                    # Minimum affected failed transactions required to prevent small-sample flukes
BASELINE_WINDOW_HOURS = 7 * 24            # 7 days baseline
OBSERVATION_WINDOW_HOURS = 24             # Recent window

# Anomaly Thresholds
FAILURE_RATE_DEVIATION_THRESHOLD = 100.0  # +100% (doubling of failure rate)
LATENCY_DEVIATION_THRESHOLD = 150.0       # +150% latency increase
MIN_ABSOLUTE_RATE_INCREASE = 0.04         # +4% absolute rate increase required to avoid noise
Z_SCORE_THRESHOLD = 3.0                  # Statistical z-score supporting threshold
