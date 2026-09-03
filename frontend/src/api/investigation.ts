import { apiFetch } from './client';
import type { InvestigationResponse } from '../types';

export async function queryAIInvestigation(query: string, entityId?: string): Promise<InvestigationResponse> {
  return apiFetch<InvestigationResponse>('/investigation/query', {
    method: 'POST',
    body: JSON.stringify({ query, entity_id: entityId }),
  });
}

export async function investigateTransactionAI(transactionId: string): Promise<InvestigationResponse> {
  return apiFetch<InvestigationResponse>(`/investigation/transaction/${transactionId}`);
}

export async function investigateIncidentAI(incidentId: string): Promise<InvestigationResponse> {
  return apiFetch<InvestigationResponse>(`/investigation/incident/${incidentId}`);
}
