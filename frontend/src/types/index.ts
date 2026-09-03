export interface GatewayPerformance {
  gateway_id: string;
  gateway_code: string;
  gateway_name: string;
  status: 'HEALTHY' | 'DEGRADED' | 'OUTAGE';
  total_transactions: number;
  failed_transactions: number;
  failure_rate: number;
  baseline_failure_rate: number;
  revenue_at_risk: number;
}

export interface DashboardMetrics {
  total_transactions: number;
  total_transaction_value: number;
  successful_payment_value: number;
  failed_payment_value: number;
  revenue_at_risk: number;
  ground_truth_recoverable_revenue: number;
  actual_recovered_revenue: number;
  overall_failure_rate: number;
  recovery_rate: number;
  gateway_performance: GatewayPerformance[];
  active_incidents_count: number;
  active_incidents: {
    id: string;
    title: string;
    anomaly_type: string;
    baseline_rate: number;
    current_rate: number;
    revenue_at_risk: number;
    confidence: number;
    root_cause: string;
  }[];
}

export interface Incident {
  id: string;
  title: string;
  incident_type?: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'ACTIVE' | 'RESOLVED' | 'INVESTIGATING';
  gateway_id?: string;
  issuer_id?: string;
  affected_payment_method?: string;
  anomaly_type: string;
  baseline_rate: number;
  current_rate: number;
  affected_transactions: number;
  gross_revenue_at_risk: number;
  recoverable_revenue_at_risk: number;
  unrecoverable_revenue_at_risk: number;
  recovered_revenue: number;
  confidence: number;
  confidence_type: string;
  root_cause: string;
  recommended_action: string;
  evidence_json?: string;
  evidence?: Record<string, any>;
  created_at?: string;
}

export interface IncidentTimelineEvent {
  id: string;
  incident_id: string;
  event_type: string;
  description: string;
  event_data: Record<string, any>;
  timestamp: string;
}

export interface ScenarioMetrics {
  transactions_considered: number;
  eligible_transactions: number;
  predicted_recoverable_amount: number;
  gross_expected_recovery: number;
  expected_recovery_cost: number;
  expected_friction: number;
  expected_risk_penalty: number;
  expected_net_recovery: number;
  expected_attempts: number;
  expected_successes: number;
  expected_success_rate: number;
  revenue_per_action: number;
  cost_per_successful_recovery: number;
  avoided_attempts: number;
  incremental_revenue_vs_baseline: number;
  incremental_net_recovery_vs_baseline: number;
}

export interface ScenarioResult {
  scenario_name: string;
  scenario_type: string;
  parameters: {
    gateway_status_overrides: Record<string, string>;
    recoverability_threshold: number;
    strategy_overrides: Record<string, string>;
  };
  metrics: ScenarioMetrics;
  baseline_comparison?: Record<string, any>;
}

export interface ScenarioComparisonResponse {
  scenarios: ScenarioResult[];
  recommended_scenario: string;
  recommendation_reason: string;
  evidence: Array<{
    type: string;
    scenario_name: string;
    expected_net_recovery: number;
    gross_expected_recovery: number;
    expected_attempts: number;
    risk_penalty: number;
    source: string;
  }>;
}

export interface EvidenceItem {
  type: string;
  metric?: string;
  value?: any;
  baseline?: any;
  severity?: string;
  source?: string;
  strategy?: string;
  expected_economic_value?: number;
  [key: string]: any;
}

export interface InvestigationResponse {
  query: string;
  investigation_type: string;
  entity_id?: string;
  answer: string;
  confidence: string;
  confidence_type: string;
  provider_used: string;
  evidence: EvidenceItem[];
  ground_truth_context: Record<string, any>;
}

export interface RecoveryOpportunity {
  transaction_id: string;
  amount: number;
  payment_method: string;
  failure_code: string;
  failure_category: string;
  recoverability_probability: number;
  recommended_strategy: string;
  expected_economic_value: number;
  decision_confidence: string;
  autonomy_action: string;
  timestamp?: string;
}

export interface CandidateEvaluation {
  strategy: string;
  strategy_success_probability: number;
  probability_trace: Record<string, any>;
  transaction_amount: number;
  expected_recovery: number;
  recovery_cost: number;
  customer_friction_cost: number;
  risk_penalty: number;
  expected_economic_value: number;
}

export interface RecoveryDecisionResponse {
  transaction_id: string;
  transaction_amount: number;
  failure_code: string;
  failure_category: string;
  gateway_status: string;
  recoverability_model_prediction: {
    recoverability_probability: number;
  };
  decision: {
    strategy: string;
    recoverability_probability: number;
    strategy_success_probability: number;
    expected_recovery: number;
    recovery_cost: number;
    customer_friction_cost: number;
    risk_penalty: number;
    expected_economic_value: number;
    decision_confidence: string;
    confidence_type: string;
    autonomy_action: string;
    explanation: {
      strategy: string;
      reason_codes: string[];
      summary: string;
      economic_reason: string;
      confidence: string;
      confidence_type: string;
    };
    decision_trace: {
      candidate_evaluations: CandidateEvaluation[];
      viable_candidates_count: number;
      winning_strategy: string;
      winning_expected_economic_value: string;
    };
  };
}
