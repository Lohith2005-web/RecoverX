import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchRecoveryOpportunities, fetchRecoveryDecision, executeRecovery } from './recovery';
import * as clientModule from './client';

describe('RecoverX API Client - recovery.ts', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('fetchRecoveryOpportunities calls correct endpoint and returns opportunities', async () => {
    const mockData = {
      total_opportunities: 1,
      opportunities: [
        {
          transaction_id: 'txn_000040',
          amount: 4999,
          payment_method: 'UPI',
          failure_code: 'GATEWAY_TIMEOUT',
          failure_category: 'TECHNICAL_TIMEOUT',
          recoverability_probability: 0.85,
          recommended_strategy: 'GATEWAY_REROUTE',
          expected_economic_value: 4900,
          decision_confidence: 'HIGH',
          autonomy_action: 'AUTOMATED_EXECUTION'
        }
      ]
    };
    vi.spyOn(clientModule, 'apiFetch').mockResolvedValue(mockData);

    const result = await fetchRecoveryOpportunities(10);
    expect(clientModule.apiFetch).toHaveBeenCalledWith('/recovery/opportunities?limit=10');
    expect(result).toHaveLength(1);
    expect(result[0].transaction_id).toBe('txn_000040');
  });

  it('fetchRecoveryDecision calls decision endpoint for given transaction ID', async () => {
    const mockDecision = {
      transaction_id: 'txn_000040',
      transaction_amount: 4999,
      failure_code: 'GATEWAY_TIMEOUT',
      failure_category: 'TECHNICAL_TIMEOUT',
      gateway_status: 'DEGRADED',
      recoverability_model_prediction: { recoverability_probability: 0.85 },
      decision: {
        strategy: 'GATEWAY_REROUTE',
        recoverability_probability: 0.85,
        strategy_success_probability: 0.98,
        expected_recovery: 4899,
        recovery_cost: 15,
        customer_friction_cost: 5,
        risk_penalty: 0,
        expected_economic_value: 4879,
        decision_confidence: 'HIGH',
        confidence_type: 'HEURISTIC',
        autonomy_action: 'AUTOMATED_EXECUTION',
        explanation: {
          strategy: 'GATEWAY_REROUTE',
          reason_codes: ['CURRENT_GATEWAY_DEGRADED'],
          summary: 'Gateway reroute selected',
          economic_reason: 'Expected recovery exceeds costs',
          confidence: 'HIGH',
          confidence_type: 'HEURISTIC'
        },
        decision_trace: {
          candidate_evaluations: [],
          viable_candidates_count: 1,
          winning_strategy: 'GATEWAY_REROUTE',
          winning_expected_economic_value: '4879'
        }
      }
    };
    vi.spyOn(clientModule, 'apiFetch').mockResolvedValue(mockDecision);

    const result = await fetchRecoveryDecision('txn_000040');
    expect(clientModule.apiFetch).toHaveBeenCalledWith('/recovery/decision/txn_000040');
    expect(result.decision.strategy).toBe('GATEWAY_REROUTE');
  });

  it('executeRecovery posts to /recovery/execute/{id} endpoint', async () => {
    const mockExecution = {
      execution_id: 'exec_1234567890',
      decision_id: 'dec_1234567890',
      transaction_id: 'txn_000040',
      strategy: 'GATEWAY_REROUTE',
      simulated_success: true,
      recovered_amount: 4999.0,
      recovery_cost: 15.0,
      friction_cost: 5.0,
      risk_penalty: 0.0,
      net_recovered_amount: 4979.0,
      executed_at: '2026-09-05T12:00:00Z',
      is_simulated: true
    };
    vi.spyOn(clientModule, 'apiFetch').mockResolvedValue(mockExecution);

    const result = await executeRecovery('txn_000040');
    expect(clientModule.apiFetch).toHaveBeenCalledWith('/recovery/execute/txn_000040', { method: 'POST' });
    expect(result.simulated_success).toBe(true);
    expect(result.recovered_amount).toBe(4999.0);
    expect(result.is_simulated).toBe(true);
  });
});
