import React from 'react';
import { AlertTriangle, ArrowUpRight, Search, LineChart, ShieldCheck, Zap } from 'lucide-react';
import type { Incident } from '../types';
import { formatINR, formatPercent } from '../utils/formatters';
import { Badge } from './UI/Badge';

interface IncidentSpotlightProps {
  incident: Incident | null;
  onInvestigate: (incidentId: string) => void;
  onRunWhatIf: () => void;
}

export const IncidentSpotlight: React.FC<IncidentSpotlightProps> = ({
  incident,
  onInvestigate,
  onRunWhatIf,
}) => {
  if (!incident) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-3 bg-emerald-950/80 border border-emerald-800/80 rounded-xl text-emerald-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-bold text-white">Payment System Healthy</h3>
              <Badge variant="success">ACTIVE MONITORS</Badge>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              No critical or high-severity anomalies detected in observation window.
            </p>
          </div>
        </div>
        <button
          onClick={onRunWhatIf}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg shadow-md transition-all flex items-center space-x-2 shrink-0"
        >
          <LineChart className="w-4 h-4" />
          <span>Run What-If Counterfactual</span>
        </button>
      </div>
    );
  }

  const deviation = incident.baseline_rate > 0
    ? ((incident.current_rate - incident.baseline_rate) / incident.baseline_rate) * 100
    : 0;

  return (
    <div className="relative overflow-hidden bg-gradient-to-r from-red-950/40 via-slate-900 to-slate-900 border-2 border-red-800/80 rounded-xl p-6 shadow-2xl shadow-red-950/30">
      {/* Decorative Glow */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-red-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-red-900/40">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-red-950 border border-red-800 rounded-xl text-red-400 animate-pulse">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-extrabold uppercase tracking-widest text-red-400">
                ACTIVE INCIDENT SPOTLIGHT
              </span>
              <Badge variant="danger">{incident.severity}</Badge>
              <span className="text-xs text-slate-400 font-mono">#{incident.id}</span>
            </div>
            <h3 className="text-lg font-bold text-white mt-0.5">{incident.title}</h3>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2 shrink-0">
          <button
            onClick={() => onInvestigate(incident.id)}
            className="px-4 py-2 bg-red-900/80 hover:bg-red-800 border border-red-700 text-white text-xs font-bold rounded-lg transition-all flex items-center space-x-1.5 shadow-lg shadow-red-950/50"
          >
            <Search className="w-3.5 h-3.5" />
            <span>Investigate Incident</span>
          </button>
          <button
            onClick={onRunWhatIf}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg transition-all flex items-center space-x-1.5 shadow-lg shadow-blue-900/40"
          >
            <LineChart className="w-3.5 h-3.5" />
            <span>Run What-If</span>
          </button>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 py-4 border-b border-slate-800/80">
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Failure Rate</p>
          <p className="text-xl font-bold text-red-400 mt-0.5 font-mono">
            {formatPercent(incident.current_rate, true)}
          </p>
        </div>
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Historical Baseline</p>
          <p className="text-xl font-bold text-slate-300 mt-0.5 font-mono">
            {formatPercent(incident.baseline_rate, true)}
          </p>
        </div>
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Percentage Deviation</p>
          <p className="text-xl font-bold text-amber-400 mt-0.5 font-mono flex items-center">
            <ArrowUpRight className="w-4 h-4 mr-0.5" />
            {formatPercent(deviation, false, true)}
          </p>
        </div>
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Revenue at Risk</p>
          <p className="text-xl font-bold text-white mt-0.5 font-mono">
            {formatINR(incident.gross_revenue_at_risk, 'compact')}
          </p>
        </div>
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Oracle Recoverable</p>
          <p className="text-xl font-bold text-emerald-400 mt-0.5 font-mono">
            {formatINR(incident.recoverable_revenue_at_risk, 'compact')}
          </p>
          <span className="text-[10px] text-slate-400 block mt-0.5">Simulator benchmark ground truth</span>
        </div>
      </div>

      {/* Root Cause Summary Footer */}
      <div className="pt-3 flex items-start space-x-2">
        <Zap className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <p className="text-xs text-slate-300 leading-relaxed font-medium">
          <strong className="text-amber-300 font-semibold">Root Cause: </strong>
          {incident.root_cause || 'Infrastructure degradation detected causing elevated technical timeout errors.'}
        </p>
      </div>
    </div>
  );
};
