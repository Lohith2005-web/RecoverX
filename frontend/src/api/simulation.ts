import { apiFetch } from './client';
import type { ScenarioComparisonResponse, ScenarioResult } from '../types';

export interface CompareScenariosPayload {
  scenarios: Array<{
    name: string;
    type: string;
    gateway_status_overrides?: Record<string, string>;
    recoverability_threshold?: number;
    strategy_overrides?: Record<string, string>;
  }>;
  observation_hours?: number;
}

export async function compareScenarios(payload: CompareScenariosPayload): Promise<ScenarioComparisonResponse> {
  return apiFetch<ScenarioComparisonResponse>('/simulation/compare', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function runSingleScenario(scenario: CompareScenariosPayload['scenarios'][0]): Promise<ScenarioResult> {
  return apiFetch<ScenarioResult>('/simulation/what-if', {
    method: 'POST',
    body: JSON.stringify(scenario),
  });
}
