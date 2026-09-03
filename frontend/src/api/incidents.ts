import { apiFetch } from './client';
import type { Incident, IncidentTimelineEvent } from '../types';

export async function fetchIncidents(statusFilter?: string): Promise<Incident[]> {
  const query = statusFilter ? `?status_filter=${statusFilter}` : '';
  const res = await apiFetch<{ active_incidents_count: number; incidents: Incident[] }>(`/incidents${query}`);
  return res.incidents || [];
}

export async function fetchIncidentById(incidentId: string): Promise<Incident> {
  return apiFetch<Incident>(`/incidents/${incidentId}`);
}

export async function fetchIncidentTimeline(incidentId: string): Promise<IncidentTimelineEvent[]> {
  const res = await apiFetch<{ incident_id: string; total_events: number; timeline: IncidentTimelineEvent[] }>(`/incidents/${incidentId}/timeline`);
  return res.timeline || [];
}

export async function fetchIncidentImpact(incidentId: string): Promise<Record<string, any>> {
  return apiFetch<Record<string, any>>(`/incidents/${incidentId}/impact`);
}
