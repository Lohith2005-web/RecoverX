import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Badge } from './UI/Badge';

interface KPICardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: LucideIcon;
  variant?: 'danger' | 'warning' | 'success' | 'info' | 'neutral';
  badgeText?: string;
}

export const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = 'neutral',
  badgeText,
}) => {
  const variantStyles = {
    danger: {
      border: 'border-red-900/60 hover:border-red-800/80',
      iconBg: 'bg-red-950/80 text-red-400 border border-red-800/60',
      glow: 'from-red-950/20 to-transparent',
    },
    warning: {
      border: 'border-amber-900/60 hover:border-amber-800/80',
      iconBg: 'bg-amber-950/80 text-amber-400 border border-amber-800/60',
      glow: 'from-amber-950/20 to-transparent',
    },
    success: {
      border: 'border-emerald-900/60 hover:border-emerald-800/80',
      iconBg: 'bg-emerald-950/80 text-emerald-400 border border-emerald-800/60',
      glow: 'from-emerald-950/20 to-transparent',
    },
    info: {
      border: 'border-blue-900/60 hover:border-blue-800/80',
      iconBg: 'bg-blue-950/80 text-blue-400 border border-blue-800/60',
      glow: 'from-blue-950/20 to-transparent',
    },
    neutral: {
      border: 'border-slate-800/80 hover:border-slate-700/80',
      iconBg: 'bg-slate-900 text-slate-400 border border-slate-700/60',
      glow: 'from-slate-900/40 to-transparent',
    },
  };

  const style = variantStyles[variant];

  return (
    <div
      className={`relative overflow-hidden bg-slate-900/90 rounded-xl p-5 border shadow-xl transition-all ${style.border}`}
    >
      <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl ${style.glow} pointer-events-none rounded-bl-full`} />
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</p>
          <h3 className="text-2xl sm:text-3xl font-extrabold text-white mt-1 font-mono tracking-tight">{value}</h3>
          {subtitle && <p className="text-xs text-slate-400/90 mt-1">{subtitle}</p>}
        </div>
        <div className={`p-2.5 rounded-xl shrink-0 ${style.iconBg}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      {badgeText && (
        <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center justify-between">
          <Badge variant={variant}>{badgeText}</Badge>
        </div>
      )}
    </div>
  );
};
