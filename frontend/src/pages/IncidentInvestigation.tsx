import React, { useEffect, useState } from 'react';
import { AlertTriangle, ArrowLeft, ArrowUpRight, Zap, Clock, CheckCircle2 } from 'lucide-react';
import { fetchIncidentById, fetchIncidents, fetchIncidentTimeline } from '../api/incidents';
import type { Incident, IncidentTimelineEvent } from '../types';
import { formatINR, formatPercent } from '../utils/formatters';
import { Badge } from '../components/UI/Badge';
import { LoadingSpinner } from '../components/UI/LoadingSpinner';
import { ErrorAlert } from '../components/UI/ErrorAlert';
import { InvestigationPanel } from '../components/InvestigationPanel';

interface IncidentInvestigationProps {
  selectedIncidentId?: string | null;
  onBack: () => void;
  onRunWhatIf: () => void;
}

export const IncidentInvestigation: React.FC<IncidentInvestigationProps> = ({
  selectedIncidentId,
  onBack,
  onRunWhatIf,
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [incident, setIncident] = useState<Incident | null>(null);
  const [timeline, setTimeline] = useState<IncidentTimelineEvent[]>([]);
  const [allIncidents, setAllIncidents] = useState<Incident[]>([]);

  const loadData = async (targetId?: string | null) => {
    setLoading(true);
    setError(null);
    try {
      // Fetch incidents list
      const list = await fetchIncidents();
      setAllIncidents(list);

      let target: Incident | null = null;
      if (targetId) {
        try {
          target = await fetchIncidentById(targetId);
        } catch {
          // Fallback to searching list
          target = list.find((i) => i.id === targetId) || null;
        }
      }

      if (!target && list.length > 0) {
        target = list[0];
      }

      setIncident(target);

      if (target) {
        try {
          const tList = await fetchIncidentTimeline(target.id);
          setTimeline(tList);
        } catch {
          setTimeline([]);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch incident investigation data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(selectedIncidentId);
  }, [selectedIncidentId]);

  if (loading) {
    return <LoadingSpinner label="Loading incident telemetry & evidence trail..." />;
  }

  if (error || !incident) {
    return <ErrorAlert title="Incident Investigation Failure" message={error || 'No incident found to investigate.'} onRetry={() => loadData(selectedIncidentId)} />;
  }

  const deviation = incident.baseline_rate > 0
    ? ((incident.current_rate - incident.baseline_rate) / incident.baseline_rate) * 100
    : 0;

  return (
    <div className="space-y-6">
      {/* Top Header & Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors border border-slate-700"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold text-white">Incident Intelligence & Evidence Audit</h1>
              <Badge variant="danger">{incident.severity}</Badge>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Incident ID: {incident.id} | Anomaly: {incident.anomaly_type}
            </p>
          </div>
        </div>

        {/* Incident Selector Dropdown */}
        {allIncidents.length > 1 && (
          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-400">Select Incident:</span>
            <select
              value={incident.id}
              onChange={(e) => loadData(e.target.value)}
              className="bg-slate-950 border border-slate-800 text-xs text-slate-200 rounded-lg px-3 py-1.5 font-mono outline-none focus:border-blue-500"
            >
              {allIncidents.map((inc) => (
                <option key={inc.id} value={inc.id}>
                  {inc.id} - {inc.title} ({inc.severity})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Main Incident Card */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div className="flex items-start space-x-3">
            <div className="p-3 bg-red-950/80 border border-red-800 rounded-xl text-red-400 shrink-0">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-mono font-bold text-red-400 uppercase">
                  {incident.status} ANOMALY
                </span>
                <span className="text-xs text-slate-500 font-mono">
                  Confidence: {(incident.confidence * 100).toFixed(0)}% ({incident.confidence_type || 'heuristic'})
                </span>
              </div>
              <h2 className="text-xl font-bold text-white mt-1">{incident.title}</h2>
            </div>
          </div>

          <button
            onClick={onRunWhatIf}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg transition-all shadow-md shadow-blue-900/30 flex items-center space-x-1.5 shrink-0"
          >
            <span>Simulate What-If Counterfactual</span>
            <ArrowUpRight className="w-4 h-4" />
          </button>
        </div>

        {/* Telemetry Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
            <p className="text-[11px] font-semibold text-slate-400 uppercase">Current Failure Rate</p>
            <p className="text-2xl font-bold text-red-400 mt-1 font-mono">{formatPercent(incident.current_rate, true)}</p>
          </div>
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
            <p className="text-[11px] font-semibold text-slate-400 uppercase">Historical Baseline</p>
            <p className="text-2xl font-bold text-slate-300 mt-1 font-mono">{formatPercent(incident.baseline_rate, true)}</p>
          </div>
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
            <p className="text-[11px] font-semibold text-slate-400 uppercase">Percentage Deviation</p>
            <p className="text-2xl font-bold text-amber-400 mt-1 font-mono">{formatPercent(deviation, false, true)}</p>
          </div>
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
            <p className="text-[11px] font-semibold text-slate-400 uppercase">Affected Transactions</p>
            <p className="text-2xl font-bold text-white mt-1 font-mono">{incident.affected_transactions || 81}</p>
          </div>
        </div>

        {/* Root Cause Card */}
        <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-bold text-white">Root Cause Evidence & Diagnosis</h3>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed font-medium bg-slate-900 p-3 rounded-lg border border-slate-800">
            {incident.root_cause}
          </p>
          {incident.recommended_action && (
            <div className="flex items-center space-x-2 text-xs text-blue-400 pt-1">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              <span><strong>Recommended Action: </strong>{incident.recommended_action}</span>
            </div>
          )}
        </div>

        {/* Financial Breakdown */}
        <div>
          <h3 className="text-sm font-bold text-white mb-3">Financial Impact Breakdown</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-red-950/30 border border-red-900/60 p-4 rounded-xl">
              <p className="text-xs font-semibold text-red-300 uppercase">Gross Revenue at Risk</p>
              <p className="text-xl font-bold text-white font-mono mt-1">{formatINR(incident.gross_revenue_at_risk)}</p>
            </div>
            <div className="bg-emerald-950/30 border border-emerald-900/60 p-4 rounded-xl">
              <p className="text-xs font-semibold text-emerald-300 uppercase">Expected Recoverable</p>
              <p className="text-xl font-bold text-emerald-400 font-mono mt-1">{formatINR(incident.recoverable_revenue_at_risk)}</p>
            </div>
            <div className="bg-slate-950 border border-slate-800 p-4 rounded-xl">
              <p className="text-xs font-semibold text-slate-400 uppercase">Unrecoverable Risk</p>
              <p className="text-xl font-bold text-slate-400 font-mono mt-1">{formatINR(incident.unrecoverable_revenue_at_risk)}</p>
            </div>
          </div>
        </div>

        {/* Timeline Trail */}
        {timeline.length > 0 && (
          <div className="space-y-3 pt-2 border-t border-slate-800">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <Clock className="w-4 h-4 text-blue-400" />
              <span>Incident Audit Timeline</span>
            </h3>
            <div className="space-y-2">
              {timeline.map((evt) => (
                <div key={evt.id} className="bg-slate-950 p-3 rounded-lg border border-slate-800 flex items-start justify-between text-xs">
                  <div>
                    <span className="font-bold text-blue-400 uppercase font-mono text-[10px]">{evt.event_type}</span>
                    <p className="text-slate-300 mt-0.5">{evt.description}</p>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono shrink-0 ml-2">{evt.timestamp}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* AI INVESTIGATION ASSISTANT */}
      <InvestigationPanel
        entityId={incident.id}
        initialQuery={`Why is ${incident.title} considered degraded?`}
        suggestedQuestions={[
          `Why is ${incident.title} considered degraded?`,
          `What is the root cause for incident ${incident.id}?`,
          `How much revenue is recoverable for incident ${incident.id}?`,
        ]}
      />
    </div>
  );
};
