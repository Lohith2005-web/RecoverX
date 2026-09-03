import React, { useEffect, useState } from 'react';
import { ShieldAlert, TrendingUp, DollarSign, Activity, AlertOctagon, RefreshCw } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { fetchDashboardMetrics } from '../api/dashboard';
import { fetchIncidents } from '../api/incidents';
import { fetchRecoveryDecision, fetchRecoveryOpportunities } from '../api/recovery';
import type { DashboardMetrics, Incident, CandidateEvaluation } from '../types';
import { formatINR, formatPercent } from '../utils/formatters';
import { KPICard } from '../components/KPICard';
import { IncidentSpotlight } from '../components/IncidentSpotlight';
import { StrategyComparison } from '../components/StrategyComparison';
import { GatewayHealthGrid } from '../components/GatewayHealthGrid';
import { LoadingSpinner } from '../components/UI/LoadingSpinner';
import { ErrorAlert } from '../components/UI/ErrorAlert';

interface CommandCenterProps {
  onNavigateToIncident: (incidentId: string) => void;
  onNavigateToWhatIf: () => void;
}

export const CommandCenter: React.FC<CommandCenterProps> = ({
  onNavigateToIncident,
  onNavigateToWhatIf,
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [activeIncident, setActiveIncident] = useState<Incident | null>(null);
  const [sampleCandidates, setSampleCandidates] = useState<CandidateEvaluation[]>([]);
  const [winningStrategy, setWinningStrategy] = useState<string>('GATEWAY_REROUTE');
  const [sampleAmount, setSampleAmount] = useState<number>(0);
  const [sampleTxnId, setSampleTxnId] = useState<string>('');

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch dashboard metrics
      const dashData = await fetchDashboardMetrics();
      setMetrics(dashData);

      // 2. Fetch active incidents dynamically
      const incList = await fetchIncidents('ACTIVE');
      if (incList.length > 0) {
        // Select highest severity incident
        const sortedIncs = [...incList].sort((a, b) => {
          const sevMap: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
          return (sevMap[b.severity] || 0) - (sevMap[a.severity] || 0);
        });
        setActiveIncident(sortedIncs[0]);
      } else {
        setActiveIncident(null);
      }

      // 3. Fetch real strategy comparison data for a representative transaction
      const opps = await fetchRecoveryOpportunities(5);
      if (opps.length > 0) {
        const firstOpp = opps[0];
        const decData = await fetchRecoveryDecision(firstOpp.transaction_id);
        const cands = decData.decision?.decision_trace?.candidate_evaluations || [];
        setSampleCandidates(cands);
        setWinningStrategy(decData.decision.strategy);
        setSampleAmount(decData.transaction_amount);
        setSampleTxnId(decData.transaction_id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to connect to RecoverX backend API.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return <LoadingSpinner label="Loading RecoverX Command Center metrics..." />;
  }

  if (error || !metrics) {
    return <ErrorAlert title="Command Center Load Failure" message={error || 'Unable to retrieve dashboard metrics.'} onRetry={loadData} />;
  }

  // Recharts financial chart data derived strictly from backend totals
  const chartData = [
    {
      name: 'Gross Revenue at Risk',
      Amount: metrics.revenue_at_risk,
      fill: '#ef4444',
    },
    {
      name: 'Expected Recoverable',
      Amount: metrics.ground_truth_recoverable_revenue,
      fill: '#10b981',
    },
    {
      name: 'Actual Recovered',
      Amount: metrics.actual_recovered_revenue,
      fill: '#3b82f6',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight">Revenue Recovery Command Center</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Autonomous detection, economic decisioning, and counterfactual intelligence dashboard
          </p>
        </div>
        <button
          onClick={loadData}
          className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition-colors flex items-center space-x-2 shrink-0 border border-slate-700"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh Data</span>
        </button>
      </div>

      {/* TOP KPI CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Gross Revenue At Risk"
          value={formatINR(metrics.revenue_at_risk, 'compact')}
          subtitle={`Across ${metrics.failed_payment_value ? Math.round(metrics.revenue_at_risk) : 0} failed payments`}
          icon={ShieldAlert}
          variant="danger"
          badgeText="POTENTIAL LOSS"
        />
        <KPICard
          title="Expected Recoverable"
          value={formatINR(metrics.ground_truth_recoverable_revenue, 'compact')}
          subtitle="ML predicted high probability recoveries"
          icon={TrendingUp}
          variant="success"
          badgeText="ML PREDICTED"
        />
        <KPICard
          title="Actual Recovered"
          value={formatINR(metrics.actual_recovered_revenue, 'compact')}
          subtitle="Executed recovery actions"
          icon={DollarSign}
          variant="info"
          badgeText="REALIZED REVENUE"
        />
        <KPICard
          title="Active Incidents"
          value={metrics.active_incidents_count.toString()}
          subtitle="Infrastructure degradation alerts"
          icon={AlertOctagon}
          variant={metrics.active_incidents_count > 0 ? 'warning' : 'neutral'}
          badgeText={metrics.active_incidents_count > 0 ? 'ATTENTION REQUIRED' : 'HEALTHY'}
        />
      </div>

      {/* ACTIVE INCIDENT SPOTLIGHT */}
      <IncidentSpotlight
        incident={activeIncident}
        onInvestigate={onNavigateToIncident}
        onRunWhatIf={onNavigateToWhatIf}
      />

      {/* STRATEGY COMPARISON SECTION */}
      {sampleCandidates.length > 0 && (
        <StrategyComparison
          candidates={sampleCandidates}
          winningStrategy={winningStrategy}
          transactionAmount={sampleAmount}
          transactionId={sampleTxnId}
        />
      )}

      {/* REVENUE RECOVERY VISUALIZATION & GATEWAY HEALTH GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recharts Column Chart */}
        <div className="lg:col-span-1 bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-bold text-white">Revenue Distribution Breakdown</h3>
              <Activity className="w-4 h-4 text-blue-400" />
            </div>
            <p className="text-[11px] text-slate-400 mb-4">
              Financial summary derived from database transactions
            </p>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 10 }} interval={0} angle={-15} textAnchor="end" />
                  <YAxis stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}K`} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }}
                    formatter={(value: any) => [formatINR(Number(value)), 'Amount']}
                  />
                  <Bar dataKey="Amount" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800 grid grid-cols-2 gap-2 text-center text-xs">
            <div className="bg-slate-950 p-2 rounded-lg border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Failure Rate</span>
              <span className="font-mono font-bold text-red-400">{formatPercent(metrics.overall_failure_rate, true)}</span>
            </div>
            <div className="bg-slate-950 p-2 rounded-lg border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Recovery Rate</span>
              <span className="font-mono font-bold text-emerald-400">{formatPercent(metrics.recovery_rate, true)}</span>
            </div>
          </div>
        </div>

        {/* Gateway Infrastructure Health Grid */}
        <div className="lg:col-span-2">
          <GatewayHealthGrid gateways={metrics.gateway_performance} />
        </div>
      </div>
    </div>
  );
};
