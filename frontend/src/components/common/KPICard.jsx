import React from 'react';

export default function KPICard({
  label,
  value,
  unit,
  description,
  icon: Icon,
  variant = 'brand',
}) {
  const variantStyles = {
    brand: 'border-brand-500/20 bg-navy-900/90 text-brand-400 group-hover:border-brand-500/40',
    emerald: 'border-emerald-500/20 bg-navy-900/90 text-emerald-400 group-hover:border-emerald-500/40',
    amber: 'border-amber-500/20 bg-navy-900/90 text-amber-400 group-hover:border-amber-500/40',
    cyan: 'border-cyan-500/20 bg-navy-900/90 text-cyan-400 group-hover:border-cyan-500/40',
    rose: 'border-rose-500/20 bg-navy-900/90 text-rose-400 group-hover:border-rose-500/40',
  };

  const selectedVariant = variantStyles[variant] || variantStyles.brand;

  return (
    <div className={`group relative p-5 rounded-xl border ${selectedVariant} transition-all duration-200 hover:shadow-lg hover:shadow-black/40`}>
      <div className="flex items-center justify-between gap-3 mb-2">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</span>
        {Icon && (
          <div className="p-2 rounded-lg bg-navy-800/80 border border-slate-700/50">
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="flex items-baseline gap-1.5 mb-1.5">
        <span className="text-3xl font-bold tracking-tight text-white font-mono">
          {typeof value === 'number' ? value.toLocaleString() : value ?? '0'}
        </span>
        {unit && <span className="text-sm font-medium text-slate-400">{unit}</span>}
      </div>

      {description && (
        <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
          {description}
        </p>
      )}
    </div>
  );
}

