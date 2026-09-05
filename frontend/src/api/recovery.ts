import { apiFetch } from './client';
import type { RecoveryOpportunity, RecoveryDecisionResponse, ExecutionResult } from '../types';

export async function fetchRecoveryOpportunities(limit = 20): Promise<RecoveryOpportunity[]> {
  const res = await apiFetch<{ total_opportunities: number; opportunities: RecoveryOpportunity[] }>(`/recovery/opportunities?limit=${limit}`);
  return res.opportunities || [];
}

export async function fetchRecoveryDecision(transactionId: string): Promise<RecoveryDecisionResponse> {
  return apiFetch<RecoveryDecisionResponse>(`/recovery/decision/${transactionId}`);
}

export async function executeRecovery(transactionId: string, decisionId?: string, seed?: number): Promise<ExecutionResult> {
  let url = `/recovery/execute/${transactionId}`;
  const params: string[] = [];
  if (decisionId) params.push(`decision_id=${encodeURIComponent(decisionId)}`);
  if (seed !== undefined) params.push(`seed=${seed}`);
  if (params.length > 0) url += `?${params.join('&')}`;
  return apiFetch<ExecutionResult>(url, { method: 'POST' });
}

