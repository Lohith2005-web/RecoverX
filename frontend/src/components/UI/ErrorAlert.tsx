import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorAlertProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  title = 'Data Fetch Error',
  message,
  onRetry,
}) => {
  return (
    <div className="bg-red-950/40 border border-red-800/60 rounded-xl p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 my-4">
      <div className="flex items-start space-x-3">
        <AlertTriangle className="w-6 h-6 text-red-400 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-red-200 font-semibold text-sm">{title}</h4>
          <p className="text-red-300/80 text-xs mt-1 leading-relaxed">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-3.5 py-1.5 bg-red-900/60 hover:bg-red-800/80 border border-red-700/60 text-red-200 text-xs font-medium rounded-lg transition-colors flex items-center space-x-2 shrink-0"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
};
