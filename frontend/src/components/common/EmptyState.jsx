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
    <div className="flex flex-col items-center justify-center p-12 text-center rounded-2xl border border-dashed border-slate-300 bg-white shadow-sm my-6">
      <div className="w-16 h-16 rounded-2xl bg-[#EEF2FF] border border-[#CBD5E1] flex items-center justify-center text-[#4F46E5] mb-5 shadow-sm">
        <Icon className="w-8 h-8" />
      </div>

      <h3 className="text-lg font-bold text-[#0F172A] mb-2">{title}</h3>
      <p className="text-sm text-[#64748B] max-w-md mb-6 leading-relaxed">
        {description}
      </p>

      {actionText && actionTo && (
        <Link
          to={actionTo}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#4F46E5] hover:bg-[#4338CA] text-white font-semibold text-sm transition-all shadow-sm active:scale-95"
        >
          <span>{actionText}</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      )}
    </div>
  );
}

