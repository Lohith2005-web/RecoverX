import { apiFetch } from './client';
import type { RecoveryOpportunity, RecoveryDecisionResponse } from '../types';

export async function fetchRecoveryOpportunities(limit = 20): Promise<RecoveryOpportunity[]> {
  const res = await apiFetch<{ total_opportunities: number; opportunities: RecoveryOpportunity[] }>(`/recovery/opportunities?limit=${limit}`);
  return res.opportunities || [];
}

export async function fetchRecoveryDecision(transactionId: string): Promise<RecoveryDecisionResponse> {
  return apiFetch<RecoveryDecisionResponse>(`/recovery/decision/${transactionId}`);
}
