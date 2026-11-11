import React from 'react';
import { CheckCircle2, XCircle, AlertTriangle, Clock, Activity, MinusCircle } from 'lucide-react';

export default function AgentStatusBadge({ status, label, showIcon = true, size = 'md' }) {
  const normStatus = String(status || '').toLowerCase();

  let styles = 'bg-slate-800 text-slate-300 border-slate-700';
  let Icon = MinusCircle;
  let text = label || status || 'Unknown';

  switch (normStatus) {
    case 'completed':
    case 'operational':
    case 'success':
    case 'passed':
    case 'valid':
      styles = 'bg-emerald-950/60 text-emerald-300 border-emerald-800/80 shadow-sm shadow-emerald-950/50';
      Icon = CheckCircle2;
      text = label || (normStatus === 'operational' ? 'Operational' : 'Completed');
      break;

    case 'passed_with_warnings':
    case 'warning':
    case 'weakly_relevant':
      styles = 'bg-amber-950/60 text-amber-300 border-amber-800/80 shadow-sm shadow-amber-950/50';
      Icon = AlertTriangle;
      text = label || (normStatus === 'weakly_relevant' ? 'Weakly Related' : 'Passed w/ Warnings');
      break;

    case 'failed':
    case 'invalid':
    case 'error':
      styles = 'bg-rose-950/60 text-rose-300 border-rose-800/80 shadow-sm shadow-rose-950/50';
      Icon = XCircle;
      text = label || 'Failed';
      break;

    case 'running':
    case 'executing':
      styles = 'bg-indigo-950/60 text-indigo-300 border-indigo-700 animate-pulse shadow-sm shadow-indigo-950/50';
      Icon = Activity;
      text = label || 'Executing...';
      break;

    case 'skipped':
      styles = 'bg-slate-800/80 text-slate-400 border-slate-700/80';
      Icon = Clock;
      text = label || 'Skipped';
      break;

    default:
      styles = 'bg-navy-800 text-slate-300 border-slate-700';
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

