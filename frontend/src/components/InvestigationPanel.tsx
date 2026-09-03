import React, { useState } from 'react';
import { Bot, Send, Sparkles, AlertCircle } from 'lucide-react';
import { queryAIInvestigation } from '../api/investigation';
import type { InvestigationResponse } from '../types';
import { EvidencePanel } from './EvidencePanel';
import { Badge } from './UI/Badge';

interface InvestigationPanelProps {
  entityId?: string;
  initialQuery?: string;
  suggestedQuestions?: string[];
}

export const InvestigationPanel: React.FC<InvestigationPanelProps> = ({
  entityId,
  initialQuery = '',
  suggestedQuestions = [
    'Why did RecoverX choose gateway reroute?',
    'What happens if Gateway B remains degraded?',
    'How much revenue is currently at risk?',
    'Why is Gateway B considered degraded?',
  ],
}) => {
  const [inputQuery, setInputQuery] = useState(initialQuery);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<InvestigationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (queryText: string) => {
    if (!queryText.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await queryAIInvestigation(queryText, entityId);
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Failed to process AI investigation query.');
    } finally {
      setLoading(false);
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(inputQuery);
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-xl space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 bg-blue-950 border border-blue-800/80 rounded-lg text-blue-400">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-bold text-white">RecoverX AI Investigation Assistant</h3>
              <Badge variant="info">EVIDENCE-GROUNDED</Badge>
            </div>
            <p className="text-xs text-slate-400">
              Grounded strictly in RecoverX engine metrics and backend evidence bundles
            </p>
          </div>
        </div>
      </div>

      {/* Suggested Questions */}
      <div className="flex flex-wrap gap-2">
        {suggestedQuestions.map((q, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => {
              setInputQuery(q);
              handleSearch(q);
            }}
            className="px-3 py-1.5 bg-slate-950 hover:bg-slate-800/80 border border-slate-800 text-slate-300 hover:text-white text-xs rounded-lg transition-colors flex items-center space-x-1.5"
          >
            <Sparkles className="w-3 h-3 text-blue-400 shrink-0" />
            <span>{q}</span>
          </button>
        ))}
      </div>

      {/* Search Input */}
      <form onSubmit={handleFormSubmit} className="flex items-center space-x-2">
        <input
          type="text"
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          placeholder="Ask RecoverX about failure root cause, what-if impact, or strategy decisions..."
          className="flex-1 bg-slate-950 border border-slate-800 focus:border-blue-500 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 outline-none transition-all font-sans"
        />
        <button
          type="submit"
          disabled={loading || !inputQuery.trim()}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-blue-900/40 disabled:opacity-50 flex items-center space-x-1.5 shrink-0"
        >
          {loading ? (
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <Send className="w-3.5 h-3.5" />
              <span>Investigate</span>
            </>
          )}
        </button>
      </form>

      {/* Error Message */}
      {error && (
        <div className="p-3 bg-red-950/40 border border-red-800/60 rounded-xl text-xs text-red-300 flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Answer Output */}
      {result && (
        <div className="bg-slate-950 border border-slate-800/90 rounded-xl p-5 space-y-4 shadow-inner">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-900 pb-3">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-slate-300">Investigation Result</span>
              <Badge variant={result.confidence === 'HIGH' ? 'success' : 'warning'}>
                {result.confidence} CONFIDENCE
              </Badge>
            </div>
            <div className="flex items-center space-x-2 text-[11px] text-slate-400 font-mono">
              <span>Provider:</span>
              <span className="px-2 py-0.5 bg-slate-900 border border-slate-800 rounded text-blue-400">
                {result.provider_used === 'FallbackLLMProvider' ? 'Evidence-Grounded Fallback' : result.provider_used}
              </span>
            </div>
          </div>

          <div className="text-xs text-slate-200 leading-relaxed font-sans bg-slate-900/60 p-4 rounded-xl border border-slate-800/60 font-medium">
            {result.answer}
          </div>

          {/* Traceable Evidence Bundle */}
          <EvidencePanel evidence={result.evidence} />
        </div>
      )}
    </div>
  );
};
