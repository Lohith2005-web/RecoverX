import React, { useEffect, useState } from 'react';
import { Search, ArrowLeft, CheckCircle2, Zap, Loader2, AlertOctagon } from 'lucide-react';
import { fetchRecoveryDecision, fetchRecoveryOpportunities, executeRecovery } from '../api/recovery';
import type { RecoveryDecisionResponse, RecoveryOpportunity, CandidateEvaluation, ExecutionResult } from '../types';
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

  // Execution flow state
  const [executing, setExecuting] = useState<boolean>(false);
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);

  const loadOpportunitiesAndTransaction = async (targetId?: string) => {
    setLoading(true);
    setError(null);
    setExecutionResult(null);
    setExecutionError(null);
    try {
      // 1. Fetch available failed transactions list for dropdown
      const oppList = await fetchRecoveryOpportunities(20);
      setOpportunities(oppList);

      const idToFetch = targetId || (initialTransactionId ? initialTransactionId : oppList.length > 0 ? oppList[0].transaction_id : 'txn_000040');
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

  const handleExecuteRecovery = async () => {
    if (!decisionData || executing) return;
    setExecuting(true);
    setExecutionError(null);
    setExecutionResult(null);

    try {
      const result = await executeRecovery(decisionData.transaction_id);
      setExecutionResult(result);

      // Refresh transaction decision & state after execution
      const refreshed = await fetchRecoveryDecision(decisionData.transaction_id);
      setDecisionData(refreshed);

      // Refresh opportunities list
      const oppList = await fetchRecoveryOpportunities(20);
      setOpportunities(oppList);
    } catch (err: any) {
      setExecutionError(err.message || 'Recovery execution failed.');
    } finally {
      setExecuting(false);
    }
  };

  const candidateList: CandidateEvaluation[] = decisionData?.decision?.decision_trace?.candidate_evaluations || [];

  const winningStrategy = decisionData?.decision?.strategy || 'DO_NOT_ACT';
  const explanation = decisionData?.decision?.explanation;
  const pMl = decisionData?.recoverability_model_prediction?.recoverability_probability || 0;
  const isAlreadyRecovered = decisionData?.status === 'RECOVERED';
  const isExecutable =
    !!decisionData &&
    winningStrategy !== 'DO_NOT_ACT' &&
    decisionData.decision?.autonomy_action !== 'DO_NOT_ACT' &&
    !isAlreadyRecovered;


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
              placeholder="e.g. txn_000040"
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

            {/* RECOVERY EXECUTION ACTION CARD */}
            {isAlreadyRecovered ? (
              <div className="bg-emerald-950/40 border border-emerald-500/50 p-4 rounded-xl flex items-center justify-between font-mono text-xs text-emerald-200">
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <div>
                    <span className="font-bold text-white uppercase block">TRANSACTION RECOVERED</span>
                    <span className="text-[11px] text-emerald-300">
                      Successfully recovered via <strong className="text-white">{winningStrategy}</strong>
                    </span>
                  </div>
                </div>
                {decisionData.recovered_amount !== undefined && (
                  <Badge variant="success">Recovered {formatINR(decisionData.recovered_amount)}</Badge>
                )}
              </div>
            ) : isExecutable ? (
              <div className="bg-gradient-to-r from-slate-950 via-slate-900 to-blue-950/70 p-5 rounded-xl border border-blue-900/60 shadow-lg space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center space-x-2">
                      <Zap className="w-4 h-4 text-blue-400 animate-pulse" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">Recommended Execution Action</span>
                      <Badge variant="info">{winningStrategy}</Badge>
                    </div>
                    <p className="text-xs text-slate-300 mt-1">
                      Execute backend decision engine strategy for transaction <span className="font-mono text-white font-bold">{decisionData.transaction_id}</span>.
                    </p>
                  </div>

                  <button
                    onClick={handleExecuteRecovery}
                    disabled={executing || !!executionResult}
                    className={`px-5 py-2.5 rounded-xl text-xs font-bold font-mono transition-all flex items-center justify-center space-x-2 shadow-lg ${
                      executing || executionResult
                        ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                        : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/50 border border-emerald-500/50 hover:scale-[1.02] active:scale-[0.98]'
                    }`}
                  >
                    {executing ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                        <span>EXECUTING RECOVERY...</span>
                      </>
                    ) : (
                      <>
                        <Zap className="w-4 h-4" />
                        <span>EXECUTE RECOMMENDED RECOVERY</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Outcome Display */}
                {executionResult && (
                  <div className={`p-4 rounded-xl border font-mono text-xs space-y-2.5 ${
                    executionResult.simulated_success
                      ? 'bg-emerald-950/80 border-emerald-600/70 text-emerald-200'
                      : 'bg-red-950/80 border-red-600/70 text-red-200'
                  }`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        {executionResult.simulated_success ? (
                          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                        ) : (
                          <AlertOctagon className="w-5 h-5 text-red-400" />
                        )}
                        <span className="font-bold text-sm">
                          {executionResult.simulated_success
                            ? 'RECOVERY EXECUTION SUCCESSFUL'
                            : 'RECOVERY EXECUTION COMPLETED WITH FAILURE'}
                        </span>
                      </div>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-800">
                        Simulated Recovery
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-800/80 text-[11px]">
                      <div>
                        <span className="text-slate-400 block text-[10px]">Strategy Executed</span>
                        <span className="font-bold text-white">{executionResult.strategy}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Recovered Amount</span>
                        <span className="font-bold text-emerald-400">{formatINR(executionResult.recovered_amount)}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Net Economic Value</span>
                        <span className="font-bold text-blue-300">{formatINR(executionResult.net_recovered_amount)}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Execution ID</span>
                        <span className="font-mono text-slate-300">{executionResult.execution_id}</span>
                      </div>
                    </div>

                    <p className="text-[11px] text-amber-300/90 pt-1 italic">
                      * Note: This is a simulated recovery execution produced by the RecoverX decision engine sandbox environment, not a real payment gateway transaction.
                    </p>
                  </div>
                )}

                {executionError && (
                  <div className="p-3 bg-red-950/80 border border-red-800 rounded-xl text-red-300 text-xs font-mono">
                    Execution Error: {executionError}
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800/80 font-mono text-xs text-slate-400 flex items-center justify-between">
                <span>Execution Policy Gate: Action not recommended or blocked (`{winningStrategy}`)</span>
                <Badge variant="warning">NO RECOVERY ACTION</Badge>
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
