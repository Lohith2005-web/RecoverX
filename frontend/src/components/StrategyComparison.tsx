import React from 'react';
import { CheckCircle2, DollarSign, ShieldAlert, Cpu, AlertCircle } from 'lucide-react';
import type { CandidateEvaluation } from '../types';
import { formatINR, formatPercent } from '../utils/formatters';
import { Badge } from './UI/Badge';

interface StrategyComparisonProps {
  candidates: CandidateEvaluation[];
  winningStrategy: string;
  transactionAmount?: number;
  transactionId?: string;
}

export const StrategyComparison: React.FC<StrategyComparisonProps> = ({
  candidates,
  winningStrategy,
  transactionAmount,
  transactionId,
}) => {
  const strategyIcons: Record<string, React.FC<{ className?: string }>> = {
    SMART_RETRY: Cpu,
    GATEWAY_REROUTE: DollarSign,
    PAYMENT_METHOD_RECOVERY: CheckCircle2,
    CUSTOMER_RECOVERY: ShieldAlert,
    DO_NOT_ACT: AlertCircle,
  };

  const strategyLabels: Record<string, string> = {
    SMART_RETRY: 'Smart Retry',
    GATEWAY_REROUTE: 'Gateway Reroute',
    PAYMENT_METHOD_RECOVERY: 'Payment Method Recovery',
    CUSTOMER_RECOVERY: 'Customer Recovery',
    DO_NOT_ACT: 'Do Not Act',
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-base font-bold text-white">Economic Recovery Strategy Evaluator</h3>
            <Badge variant="info">PHASE 3 ENGINE</Badge>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            EV Maximization: Net Economic Value = Gross Recovery - (Cost + Friction + Risk Penalty)
            {transactionAmount ? ` for Transaction ₹${transactionAmount.toLocaleString('en-IN')}` : ''}
            {transactionId ? ` (${transactionId})` : ''}
          </p>
        </div>
        <div className="flex items-center space-x-1 text-[11px] text-slate-400 bg-slate-950 px-3 py-1 rounded-lg border border-slate-800 font-mono">
          <span>Winner:</span>
          <span className="font-bold text-emerald-400">{winningStrategy}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {candidates.map((cand) => {
          const isWinner = cand.strategy === winningStrategy;
          const Icon = strategyIcons[cand.strategy] || Cpu;
          const label = strategyLabels[cand.strategy] || cand.strategy;
          const ev = cand.expected_economic_value;

          return (
            <div
              key={cand.strategy}
              className={`relative rounded-xl p-4 border transition-all flex flex-col justify-between ${
                isWinner
                  ? 'bg-gradient-to-b from-blue-950/80 to-slate-900 border-2 border-blue-500 shadow-xl shadow-blue-950/40'
                  : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700/80'
              }`}
            >
              {isWinner && (
                <div className="absolute -top-2.5 right-3 px-2 py-0.5 bg-blue-600 text-white text-[10px] font-bold uppercase tracking-wider rounded-full shadow-md">
                  SELECTED STRATEGY
                </div>
              )}

              <div>
                <div className="flex items-center space-x-2.5">
                  <div
                    className={`p-2 rounded-lg ${
                      isWinner ? 'bg-blue-600 text-white' : 'bg-slate-900 text-slate-400 border border-slate-800'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-white">{label}</h4>
                    <p className="text-[10px] text-slate-400 font-mono">{cand.strategy}</p>
                  </div>
                </div>

                <div className="mt-4 space-y-2 text-xs">
                  <div className="flex justify-between items-center pb-1 border-b border-slate-800/60">
                    <span className="text-slate-400">Expected Net EV:</span>
                    <span
                      className={`font-mono font-bold ${
                        ev > 0 ? (isWinner ? 'text-emerald-400 text-sm' : 'text-emerald-500') : 'text-slate-500'
                      }`}
                    >
                      {formatINR(ev)}
                    </span>
                  </div>

                  <div className="flex justify-between items-center text-[11px]">
                    <span className="text-slate-400">P(Success):</span>
                    <span className="font-mono text-slate-200">
                      {formatPercent(cand.strategy_success_probability, true)}
                    </span>
                  </div>

                  <div className="flex justify-between items-center text-[11px]">
                    <span className="text-slate-400">Recovery Cost:</span>
                    <span className="font-mono text-slate-300">{formatINR(cand.recovery_cost)}</span>
                  </div>

                  <div className="flex justify-between items-center text-[11px]">
                    <span className="text-slate-400">Friction Cost:</span>
                    <span className="font-mono text-slate-300">{formatINR(cand.customer_friction_cost)}</span>
                  </div>

                  <div className="flex justify-between items-center text-[11px]">
                    <span className="text-slate-400">Risk Penalty:</span>
                    <span className="font-mono text-slate-300">{formatINR(cand.risk_penalty)}</span>
                  </div>
                </div>
              </div>

              <div className="mt-3 pt-2 border-t border-slate-800/60 text-[10px] text-slate-400 flex items-center justify-between">
                <span>Gross Expected:</span>
                <span className="font-mono font-semibold text-slate-300">
                  {formatINR(cand.expected_recovery)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
