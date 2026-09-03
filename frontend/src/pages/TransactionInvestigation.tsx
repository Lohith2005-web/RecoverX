import React, { useEffect, useState } from 'react';
import { Search, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { fetchRecoveryDecision, fetchRecoveryOpportunities } from '../api/recovery';
import type { RecoveryDecisionResponse, RecoveryOpportunity, CandidateEvaluation } from '../types';
import { formatINR, formatPercent } from '../utils/formatters';
import { Badge } from '../components/UI/Badge';
import { StrategyComparison } from '../components/StrategyComparison';
import { LoadingSpinner } from '../components/UI/LoadingSpinner';
import { ErrorAlert } from '../components/UI/ErrorAlert';
import { InvestigationPanel } from '../components/InvestigationPanel';

interface TransactionInvestigationProps {
  initialTransactionId?: string;
  onBack?: () => void;
}

export const TransactionInvestigation: React.FC<TransactionInvestigationProps> = ({
  initialTransactionId,
  onBack,
}) => {
  const [searchTxnId, setSearchTxnId] = useState<string>(initialTransactionId || '');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [opportunities, setOpportunities] = useState<RecoveryOpportunity[]>([]);
  const [decisionData, setDecisionData] = useState<RecoveryDecisionResponse | null>(null);

  const loadOpportunitiesAndTransaction = async (targetId?: string) => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch available failed transactions list for dropdown
      const oppList = await fetchRecoveryOpportunities(20);
      setOpportunities(oppList);

      const idToFetch = targetId || (initialTransactionId ? initialTransactionId : oppList.length > 0 ? oppList[0].transaction_id : 'txn_001160');
      setSearchTxnId(idToFetch);

      // 2. Fetch recovery decision for target transaction
      const res = await fetchRecoveryDecision(idToFetch);
      setDecisionData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch transaction recovery decision.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOpportunitiesAndTransaction(initialTransactionId);
  }, [initialTransactionId]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchTxnId.trim()) {
      loadOpportunitiesAndTransaction(searchTxnId.trim());
    }
  };

  const candidateList: CandidateEvaluation[] = decisionData?.decision?.decision_trace?.candidate_evaluations || [];
  const winningStrategy = decisionData?.decision?.strategy || 'DO_NOT_ACT';
  const explanation = decisionData?.decision?.explanation;
  const pMl = decisionData?.recoverability_model_prediction?.recoverability_probability || 0;

  return (
    <div className="space-y-6">
      {/* Top Header & Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <div className="flex items-center space-x-3">
          {onBack && (
            <button
              onClick={onBack}
              className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors border border-slate-700"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
          )}
          <div>
            <h1 className="text-xl font-bold text-white">Transaction Recovery Decision Lookup</h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Inspect ML recoverability, EV maximization, and decision traces for individual failed payments
            </p>
          </div>
        </div>

        {/* Search Input & Opportunities Select */}
        <div className="flex items-center space-x-2">
          {opportunities.length > 0 && (
            <select
              value={searchTxnId}
              onChange={(e) => {
                setSearchTxnId(e.target.value);
                loadOpportunitiesAndTransaction(e.target.value);
              }}
              className="bg-slate-950 border border-slate-800 text-xs text-slate-200 rounded-xl px-3 py-2 font-mono outline-none focus:border-blue-500 max-w-[180px] sm:max-w-xs"
            >
              {opportunities.map((opp) => (
                <option key={opp.transaction_id} value={opp.transaction_id}>
                  {opp.transaction_id} - ₹{opp.amount.toLocaleString('en-IN')} ({opp.failure_code})
                </option>
              ))}
            </select>
          )}

          <form onSubmit={handleSearchSubmit} className="flex items-center space-x-1">
            <input
              type="text"
              value={searchTxnId}
              onChange={(e) => setSearchTxnId(e.target.value)}
              placeholder="e.g. txn_001160"
              className="bg-slate-950 border border-slate-800 text-xs text-white rounded-xl px-3 py-2 font-mono outline-none focus:border-blue-500 w-32 sm:w-40"
            />
            <button
              type="submit"
              className="p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl transition-colors shadow-md shadow-blue-900/30"
            >
              <Search className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>

      {loading && <LoadingSpinner label="Evaluating transaction recovery decision trace..." />}

      {error && <ErrorAlert title="Transaction Lookup Failure" message={error} onRetry={() => loadOpportunitiesAndTransaction(searchTxnId)} />}

      {decisionData && !loading && (
        <div className="space-y-6">
          {/* Main Transaction Telemetry Header */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-xl space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-mono font-bold text-blue-400 uppercase">FAILED TRANSACTION ID</span>
                  <Badge variant="danger">{decisionData.failure_code}</Badge>
                </div>
                <h2 className="text-2xl font-black text-white mt-1 font-mono">{decisionData.transaction_id}</h2>
              </div>

              <div className="flex items-center space-x-3 bg-slate-950 p-3 rounded-xl border border-slate-800 font-mono">
                <div>
                  <span className="text-[10px] text-slate-400 block uppercase">Transaction Amount</span>
                  <span className="text-xl font-bold text-white">{formatINR(decisionData.transaction_amount)}</span>
                </div>
              </div>
            </div>

            {/* Telemetry Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Failure Category</span>
                <p className="text-sm font-bold text-slate-200 mt-0.5 font-mono">{decisionData.failure_category}</p>
              </div>

              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Gateway Status</span>
                <p className={`text-sm font-bold mt-0.5 font-mono ${decisionData.gateway_status === 'DEGRADED' ? 'text-red-400' : 'text-emerald-400'}`}>
                  {decisionData.gateway_status}
                </p>
              </div>

              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">ML Recoverability (P_ml)</span>
                <p className="text-sm font-bold text-emerald-400 mt-0.5 font-mono">{formatPercent(pMl, true)}</p>
              </div>

              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Autonomy Action</span>
                <p className="text-sm font-bold text-blue-400 mt-0.5 font-mono">{decisionData.decision.autonomy_action}</p>
              </div>
            </div>

            {/* Decision Explanation Banner */}
            {explanation && (
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-bold text-white">Decision Summary: {explanation.summary}</span>
                  </div>
                  <Badge variant="info">{decisionData.decision.decision_confidence} CONFIDENCE</Badge>
                </div>

                <p className="text-xs text-slate-300 font-mono bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                  {explanation.economic_reason}
                </p>

                {explanation.reason_codes && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {explanation.reason_codes.map((rc, i) => (
                      <span key={i} className="px-2 py-0.5 bg-slate-900 border border-slate-800 rounded text-[10px] font-mono text-blue-400">
                        {rc}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* CANDIDATE STRATEGIES EVALUATION GRID */}
          {candidateList.length > 0 && (
            <StrategyComparison
              candidates={candidateList}
              winningStrategy={winningStrategy}
              transactionAmount={decisionData.transaction_amount}
              transactionId={decisionData.transaction_id}
            />
          )}

          {/* GROUNDED AI INVESTIGATION ASSISTANT */}
          <InvestigationPanel
            entityId={decisionData.transaction_id}
            initialQuery="Why did RecoverX choose gateway reroute?"
            suggestedQuestions={[
              'Why did RecoverX choose gateway reroute?',
              `Why was strategy ${winningStrategy} selected for ${decisionData.transaction_id}?`,
              `What is the ML recoverability probability for ${decisionData.transaction_id}?`,
            ]}
          />
        </div>
      )}
    </div>
  );
};
