import React from 'react';
import { CheckCircle2, XCircle, AlertTriangle, Clock, Activity, MinusCircle } from 'lucide-react';

export default function AgentStatusBadge({ status, label, showIcon = true, size = 'md' }) {
  const normStatus = String(status || '').toLowerCase();

  let styles = 'bg-slate-100 text-slate-700 border-slate-200';
  let Icon = MinusCircle;
  let text = label || status || 'Unknown';

  switch (normStatus) {
    case 'completed':
    case 'operational':
    case 'success':
    case 'passed':
    case 'valid':
      styles = 'bg-emerald-50 text-emerald-800 border-emerald-200 shadow-xs font-semibold';
      Icon = CheckCircle2;
      text = label || (normStatus === 'operational' ? 'Operational' : 'Completed');
      break;

    case 'passed_with_warnings':
    case 'warning':
    case 'weakly_relevant':
      styles = 'bg-amber-50 text-amber-800 border-amber-200 shadow-xs font-semibold';
      Icon = AlertTriangle;
      text = label || (normStatus === 'weakly_relevant' ? 'Weakly Related' : 'Passed w/ Warnings');
      break;

    case 'failed':
    case 'invalid':
    case 'error':
      styles = 'bg-rose-50 text-rose-800 border-rose-200 shadow-xs font-semibold';
      Icon = XCircle;
      text = label || 'Failed';
      break;

    case 'running':
    case 'executing':
      styles = 'bg-[#EEF2FF] text-[#4F46E5] border-indigo-200 animate-pulse shadow-xs font-semibold';
      Icon = Activity;
      text = label || 'Executing...';
      break;

    case 'skipped':
      styles = 'bg-slate-100 text-[#334155] border-[#E2E8F0] font-medium';
      Icon = Clock;
      text = label || 'Skipped';
      break;

    default:
      styles = 'bg-slate-100 text-[#334155] border-[#E2E8F0] font-medium';
      Icon = MinusCircle;
      text = label || status;
  }

  const sizeClasses = size === 'sm'
    ? 'text-xs px-2 py-0.5 gap-1'
    : 'text-xs px-2.5 py-1 gap-1.5 font-medium';

  return (
    <span className={`inline-flex items-center rounded-full border ${sizeClasses} ${styles}`}>
      {showIcon && <Icon className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />}
      <span className="capitalize">{text}</span>
    </span>
  );
}

