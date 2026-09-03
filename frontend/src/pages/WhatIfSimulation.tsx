import React, { useEffect, useState } from 'react';
import { LineChart, Play, CheckCircle2 } from 'lucide-react';
import { compareScenarios } from '../api/simulation';
import type { CompareScenariosPayload } from '../api/simulation';
import type { ScenarioComparisonResponse } from '../types';
import { formatINR, formatPercent } from '../utils/formatters';
import { Badge } from '../components/UI/Badge';
import { LoadingSpinner } from '../components/UI/LoadingSpinner';
import { ErrorAlert } from '../components/UI/ErrorAlert';
import { InvestigationPanel } from '../components/InvestigationPanel';

export const WhatIfSimulation: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comparisonResult, setComparisonResult] = useState<ScenarioComparisonResponse | null>(null);

  // Counterfactual custom controls
  const [gatewayStatus, setGatewayStatus] = useState<'HEALTHY' | 'DEGRADED'>('DEGRADED');
  const [threshold, setThreshold] = useState<number>(0.70);

  const defaultPayload: CompareScenariosPayload = {
    scenarios: [
      {
        name: 'Current Conditions',
        type: 'CURRENT_CONDITIONS',
        gateway_status_overrides: {},
        recoverability_threshold: 0.70,
      },
      {
        name: 'Gateway B Degraded',
        type: 'GATEWAY_DEGRADATION',
        gateway_status_overrides: { gateway_b: 'DEGRADED' },
        recoverability_threshold: 0.70,
      },
      {
        name: 'Gateway B Degraded + Reroute',
        type: 'GATEWAY_REROUTE',
        gateway_status_overrides: { gateway_b: 'DEGRADED' },
        strategy_overrides: { GATEWAY_TIMEOUT: 'GATEWAY_REROUTE' },
        recoverability_threshold: 0.70,
      },
      {
        name: 'Gateway B Degraded + Threshold 0.80',
        type: 'THRESHOLD_ADJUSTMENT',
        gateway_status_overrides: { gateway_b: 'DEGRADED' },
        recoverability_threshold: 0.80,
      },
    ],
    observation_hours: 72,
  };

  const runSimulation = async (payload = defaultPayload) => {
    setLoading(true);
    setError(null);
    try {
      const res = await compareScenarios(payload);
      setComparisonResult(res);
    } catch (err: any) {
      setError(err.message || 'Failed to execute counterfactual scenario simulation.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runSimulation();
  }, []);

  const handleCustomRun = () => {
    const customPayload: CompareScenariosPayload = {
      scenarios: [
        {
          name: 'Current Conditions',
          type: 'CURRENT_CONDITIONS',
          gateway_status_overrides: {},
          recoverability_threshold: 0.70,
        },
        {
          name: `Gateway B (${gatewayStatus}) + Threshold (${threshold.toFixed(2)})`,
          type: gatewayStatus === 'DEGRADED' ? 'GATEWAY_DEGRADATION' : 'THRESHOLD_ADJUSTMENT',
          gateway_status_overrides: { gateway_b: gatewayStatus },
          recoverability_threshold: threshold,
        },
        {
          name: `Gateway B (${gatewayStatus}) + Reroute`,
          type: 'GATEWAY_REROUTE',
          gateway_status_overrides: { gateway_b: gatewayStatus },
          strategy_overrides: { GATEWAY_TIMEOUT: 'GATEWAY_REROUTE' },
          recoverability_threshold: threshold,
        },
      ],
      observation_hours: 72,
    };
    runSimulation(customPayload);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold text-white">What-If Counterfactual Scenario Simulator</h1>
            <Badge variant="info">PURE COUNTERFACTUAL (ZERO DB MUTATION)</Badge>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Simulate payment ecosystem parameter changes & compare economic net recoveries without mutating backend database state
          </p>
        </div>
      </div>

      {/* Scenario Builder Controls */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-xl space-y-4">
        <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
          <LineChart className="w-5 h-5 text-blue-400" />
          <h2 className="text-base font-bold text-white">Interactive Scenario Parameters</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Control 1: Gateway B Status */}
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
            <label className="text-xs font-semibold text-slate-300 uppercase block">Gateway B Status Override</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setGatewayStatus('HEALTHY')}
                className={`py-2 px-3 rounded-lg text-xs font-bold transition-colors border ${
                  gatewayStatus === 'HEALTHY'
                    ? 'bg-emerald-950 text-emerald-400 border-emerald-800 shadow-md'
                    : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
                }`}
              >
                HEALTHY
              </button>
              <button
                type="button"
                onClick={() => setGatewayStatus('DEGRADED')}
                className={`py-2 px-3 rounded-lg text-xs font-bold transition-colors border ${
                  gatewayStatus === 'DEGRADED'
                    ? 'bg-red-950 text-red-400 border-red-800 shadow-md'
                    : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
                }`}
              >
                DEGRADED
              </button>
            </div>
          </div>

          {/* Control 2: Threshold Slider */}
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
            <div className="flex justify-between text-xs font-semibold text-slate-300">
              <span className="uppercase">Action Threshold</span>
              <span className="font-mono text-blue-400 font-bold">{threshold.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.50"
              max="0.95"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono">
              <span>0.50 (Aggressive)</span>
              <span>0.70 (Default)</span>
              <span>0.95 (Strict)</span>
            </div>
          </div>

          {/* Run Counterfactual Button */}
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col justify-end">
            <button
              onClick={handleCustomRun}
              disabled={loading}
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-blue-900/40 disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              {loading ? (
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>RUN COUNTERFACTUAL SIMULATION</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {loading && <LoadingSpinner label="Evaluating counterfactual scenarios across payment engine..." />}

      {error && <ErrorAlert title="Simulation Error" message={error} onRetry={() => runSimulation()} />}

      {/* SIMULATION RESULTS */}
      {comparisonResult && (
        <div className="space-y-6">
          {/* Recommended Scenario Spotlight */}
          <div className="bg-gradient-to-r from-emerald-950/40 via-slate-900 to-slate-900 border-2 border-emerald-800/80 rounded-xl p-6 shadow-xl">
            <div className="flex items-center space-x-3 pb-3 border-b border-emerald-900/40">
              <div className="p-2.5 bg-emerald-950 border border-emerald-800 rounded-xl text-emerald-400">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs font-extrabold uppercase tracking-widest text-emerald-400 font-mono">
                  BACKEND RECOMMENDED SCENARIO
                </span>
                <h3 className="text-xl font-extrabold text-white mt-0.5">
                  {comparisonResult.recommended_scenario}
                </h3>
              </div>
            </div>

            <div className="pt-4 space-y-2">
              <p className="text-xs text-slate-300 leading-relaxed font-medium bg-slate-950/80 p-4 rounded-xl border border-slate-800">
                <strong className="text-emerald-400">Decision Rationale: </strong>
                {comparisonResult.recommendation_reason}
              </p>
            </div>
          </div>

          {/* Scenario Comparison Grid / Table */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white">Evaluated Scenario Comparison Matrix</h3>
              <span className="text-xs text-slate-400 font-mono">
                Evaluated: <span className="text-white font-bold">{comparisonResult.scenarios.length}</span> counterfactuals
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left text-slate-300 font-sans">
                <thead className="text-[10px] text-slate-400 uppercase bg-slate-950 border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Scenario Name</th>
                    <th className="px-4 py-3">Expected Net Recovery</th>
                    <th className="px-4 py-3">Gross Expected</th>
                    <th className="px-4 py-3">Recovery Cost</th>
                    <th className="px-4 py-3">Risk Penalty</th>
                    <th className="px-4 py-3">Attempts</th>
                    <th className="px-4 py-3">Success Rate</th>
                    <th className="px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {comparisonResult.scenarios.map((sc, idx) => {
                    const isRec = sc.scenario_name === comparisonResult.recommended_scenario;
                    const m = sc.metrics;
                    return (
                      <tr
                        key={idx}
                        className={`transition-colors ${
                          isRec ? 'bg-emerald-950/30 font-bold border-l-4 border-l-emerald-500' : 'hover:bg-slate-950/60'
                        }`}
                      >
                        <td className="px-4 py-3.5 text-white font-sans font-semibold flex items-center space-x-2">
                          <span>{sc.scenario_name}</span>
                          {isRec && <Badge variant="success">OPTIMAL</Badge>}
                        </td>
                        <td className="px-4 py-3.5 text-emerald-400 font-bold">{formatINR(m.expected_net_recovery)}</td>
                        <td className="px-4 py-3.5 text-slate-200">{formatINR(m.gross_expected_recovery)}</td>
                        <td className="px-4 py-3.5 text-slate-400">{formatINR(m.expected_recovery_cost)}</td>
                        <td className="px-4 py-3.5 text-slate-400">{formatINR(m.expected_risk_penalty)}</td>
                        <td className="px-4 py-3.5 text-slate-300">{m.expected_attempts}</td>
                        <td className="px-4 py-3.5 text-slate-300">{formatPercent(m.expected_success_rate, true)}</td>
                        <td className="px-4 py-3.5 font-sans">
                          <Badge variant={isRec ? 'success' : 'neutral'}>
                            {isRec ? 'RECOMMENDED' : 'COUNTERFACTUAL'}
                          </Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* AI Investigation Panel */}
          <InvestigationPanel
            initialQuery="What happens if Gateway B remains degraded?"
            suggestedQuestions={[
              'What happens if Gateway B remains degraded?',
              'Why did the economic model select this scenario?',
              'How does Gateway B degradation impact net recovery?',
            ]}
          />
        </div>
      )}
    </div>
  );
};
