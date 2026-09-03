import React from 'react';

export const LoadingSpinner: React.FC<{ label?: string }> = ({ label = 'Loading command metrics...' }) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 space-y-4">
      <div className="relative w-12 h-12">
        <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-500/20 rounded-full"></div>
        <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
      <p className="text-slate-400 text-sm font-medium animate-pulse">{label}</p>
    </div>
  );
};
