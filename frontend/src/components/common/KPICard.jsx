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
    brand: 'border-[#E2E8F0] bg-white text-[#4F46E5] hover:border-indigo-300',
    emerald: 'border-[#E2E8F0] bg-white text-emerald-600 hover:border-emerald-300',
    amber: 'border-[#E2E8F0] bg-white text-amber-600 hover:border-amber-300',
    cyan: 'border-[#E2E8F0] bg-white text-blue-600 hover:border-blue-300',
    rose: 'border-[#E2E8F0] bg-white text-rose-600 hover:border-rose-300',
  };

  const selectedVariant = variantStyles[variant] || variantStyles.brand;

  return (
    <div className={`group relative p-5 rounded-xl border ${selectedVariant} bg-white shadow-sm hover:shadow-md transition-all duration-200`}>
      <div className="flex items-center justify-between gap-3 mb-2">
        <span className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">{label}</span>
        {Icon && (
          <div className="p-2 rounded-lg bg-slate-50 border border-[#E2E8F0] text-[#64748B]">
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="flex items-baseline gap-1.5 mb-1.5">
        <span className="text-3xl font-bold tracking-tight text-[#0F172A] font-mono">
          {typeof value === 'number' ? value.toLocaleString() : value ?? '0'}
        </span>
        {unit && <span className="text-sm font-medium text-[#64748B]">{unit}</span>}
      </div>

      {description && (
        <p className="text-xs text-[#64748B] leading-relaxed line-clamp-2">
          {description}
        </p>
      )}
    </div>
  );
}

