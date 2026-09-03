import React from 'react';
import { ShieldAlert, Database, FileText, TrendingUp, CheckSquare } from 'lucide-react';
import type { EvidenceItem } from '../types';
import { formatINR } from '../utils/formatters';

interface EvidencePanelProps {
  evidence: EvidenceItem[];
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({ evidence }) => {
  if (!evidence || evidence.length === 0) {
    return (
      <div className="bg-slate-950/60 rounded-xl p-4 border border-slate-800 text-xs text-slate-500 italic">
        No evidence records attached to response.
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      <h4 className="text-xs font-extrabold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
        <CheckSquare className="w-3.5 h-3.5 text-blue-400" />
        <span>Traceable Evidence Bundle ({evidence.length} items)</span>
      </h4>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {evidence.map((item, idx) => {
          const typeStr = item.type || 'evidence_item';
          let icon = Database;
          if (typeStr.includes('metric') || typeStr.includes('incident')) icon = TrendingUp;
          if (typeStr.includes('root') || typeStr.includes('alert')) icon = ShieldAlert;
          if (typeStr.includes('decision') || typeStr.includes('economic')) icon = FileText;

          const IconComponent = icon;

          return (
            <div
              key={idx}
              className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3.5 flex flex-col justify-between hover:border-slate-700/80 transition-colors"
            >
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <div className="p-1.5 bg-blue-950/60 border border-blue-800/60 rounded-lg text-blue-400">
                      <IconComponent className="w-3.5 h-3.5" />
                    </div>
                    <span className="text-[11px] font-bold uppercase tracking-wider text-blue-400 font-mono">
                      {typeStr.replace(/_/g, ' ')}
                    </span>
                  </div>
                  {item.source && (
                    <span className="text-[10px] text-slate-500 font-mono bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                      {item.source}
                    </span>
                  )}
                </div>

                <div className="mt-2.5 space-y-1 text-xs">
                  {item.metric && (
                    <div className="flex justify-between text-slate-400">
                      <span>Metric:</span>
                      <span className="font-mono text-slate-200 font-semibold">{item.metric}</span>
                    </div>
                  )}
                  {item.value !== undefined && (
                    <div className="flex justify-between text-slate-400">
                      <span>Value:</span>
                      <span className="font-mono text-white font-bold">
                        {typeof item.value === 'number' && item.value > 100
                          ? formatINR(item.value)
                          : String(item.value)}
                      </span>
                    </div>
                  )}
                  {item.baseline !== undefined && (
                    <div className="flex justify-between text-slate-400">
                      <span>Baseline:</span>
                      <span className="font-mono text-slate-300">{String(item.baseline)}</span>
                    </div>
                  )}
                  {item.strategy && (
                    <div className="flex justify-between text-slate-400">
                      <span>Strategy:</span>
                      <span className="font-mono text-emerald-400 font-bold">{item.strategy}</span>
                    </div>
                  )}
                  {item.expected_economic_value !== undefined && (
                    <div className="flex justify-between text-slate-400">
                      <span>Expected Net EV:</span>
                      <span className="font-mono text-emerald-400 font-bold">
                        {formatINR(item.expected_economic_value)}
                      </span>
                    </div>
                  )}
                  {item.root_cause && (
                    <div className="text-[11px] text-amber-300 mt-1 font-medium leading-relaxed">
                      {item.root_cause}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
