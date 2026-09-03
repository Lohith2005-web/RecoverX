import { apiFetch } from './client';
import type { DashboardMetrics } from '../types';

export async function fetchDashboardMetrics(): Promise<DashboardMetrics> {
  return apiFetch<DashboardMetrics>('/dashboard/metrics');
}
