import React from 'react';
import { AlertOctagon, CheckCircle } from 'lucide-react';
import type { GatewayPerformance } from '../types';
import { formatINR, formatPercent } from '../utils/formatters';
import { Badge } from './UI/Badge';

interface GatewayHealthGridProps {
  gateways: GatewayPerformance[];
}

export const GatewayHealthGrid: React.FC<GatewayHealthGridProps> = ({ gateways }) => {
  if (!gateways || gateways.length === 0) {
    return null;
  }

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-xl">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-base font-bold text-white">Infrastructure Gateway Health Monitors</h3>
            <Badge variant="info">PHASE 4 ANOMALY ENGINE</Badge>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time latency & failure rate tracking vs 72h historical baseline
          </p>
        </div>
        <div className="text-xs text-slate-400 font-mono">
          Monitored Gateways: <span className="text-white font-bold">{gateways.length}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {gateways.map((gtw) => {
          const isDegraded = gtw.status === 'DEGRADED' || gtw.status === 'OUTAGE';

          return (
            <div
              key={gtw.gateway_id}
              className={`rounded-xl p-4 border transition-all ${
                isDegraded
                  ? 'bg-gradient-to-b from-red-950/40 via-slate-900 to-slate-900 border-2 border-red-800/80 shadow-lg shadow-red-950/40'
                  : 'bg-slate-950/60 border-slate-800/80'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  <div
                    className={`p-2 rounded-lg ${
                      isDegraded ? 'bg-red-950 text-red-400 border border-red-800' : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    }`}
                  >
                    {isDegraded ? <AlertOctagon className="w-5 h-5" /> : <CheckCircle className="w-5 h-5" />}
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white">{gtw.gateway_name}</h4>
                    <p className="text-[11px] text-slate-400 font-mono">{gtw.gateway_code}</p>
                  </div>
                </div>
                <Badge variant={isDegraded ? 'danger' : 'success'}>{gtw.status}</Badge>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                  <p className="text-[10px] text-slate-400 uppercase font-semibold">Failure Rate</p>
                  <p className={`text-base font-bold font-mono mt-0.5 ${isDegraded ? 'text-red-400' : 'text-slate-200'}`}>
                    {formatPercent(gtw.failure_rate, true)}
                  </p>
                </div>

                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                  <p className="text-[10px] text-slate-400 uppercase font-semibold">Baseline Rate</p>
                  <p className="text-base font-bold text-slate-300 font-mono mt-0.5">
                    {formatPercent(gtw.baseline_failure_rate, true)}
                  </p>
                </div>
              </div>

              <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center justify-between text-xs font-mono">
                <span className="text-slate-400">Revenue at Risk:</span>
                <span className={`font-bold ${gtw.revenue_at_risk > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                  {formatINR(gtw.revenue_at_risk, 'compact')}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
