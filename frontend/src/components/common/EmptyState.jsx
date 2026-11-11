import React from 'react';
import { Link } from 'react-router-dom';
import { Compass, ArrowRight } from 'lucide-react';

export default function EmptyState({
  title = 'No Research Executed Yet',
  description = 'Run an autonomous research query to see live data collected, verified, and analyzed across all 4 platform agents.',
  actionText = 'Start New Research',
  actionTo = '/new-research',
  icon: Icon = Compass,
}) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center rounded-2xl border border-dashed border-slate-800 bg-navy-900/40 my-6">
      <div className="w-16 h-16 rounded-2xl bg-brand-950/80 border border-brand-800/40 flex items-center justify-center text-brand-400 mb-5 shadow-glow-indigo">
        <Icon className="w-8 h-8" />
      </div>

      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-sm text-slate-400 max-w-md mb-6 leading-relaxed">
        {description}
      </p>

      {actionText && actionTo && (
        <Link
          to={actionTo}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-medium text-sm transition-all shadow-md shadow-brand-600/25 hover:shadow-glow-indigo active:scale-95"
        >
          <span>{actionText}</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      )}
    </div>
  );
}

