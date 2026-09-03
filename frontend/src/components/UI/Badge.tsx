import React from 'react';

interface BadgeProps {
  variant?: 'danger' | 'warning' | 'success' | 'info' | 'neutral';
  children: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ variant = 'neutral', children, className = '' }) => {
  const variantStyles = {
    danger: 'bg-red-950/80 text-red-400 border-red-800/80 shadow-red-950/50',
    warning: 'bg-amber-950/80 text-amber-400 border-amber-800/80 shadow-amber-950/50',
    success: 'bg-emerald-950/80 text-emerald-400 border-emerald-800/80 shadow-emerald-950/50',
    info: 'bg-blue-950/80 text-blue-400 border-blue-800/80 shadow-blue-950/50',
    neutral: 'bg-slate-900 text-slate-400 border-slate-700/60',
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide border shadow-sm ${variantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  );
};
