import React from 'react';
import { Loader2, Bot, CheckCircle2 } from 'lucide-react';

const PIPELINE_STAGES = [
  { key: 'collector', name: 'Data Collector Agent', action: 'Querying Wikipedia MediaWiki API & page extracts...' },
  { key: 'verifier', name: 'Research Verification Agent', action: 'Auditing HTTPS, domains, schemas & timestamps...' },
  { key: 'analyst', name: 'Insight Analyst Agent', action: 'Synthesizing themes, keywords & deterministic observations...' },
  { key: 'builder', name: 'Dashboard Builder Agent', action: 'Generating safe declarative dashboard specification...' },
];

export default function LoadingState({ topic, limit = 5 }) {
  return (
    <div className="p-8 rounded-2xl border border-[#E2E8F0] bg-white shadow-md my-6 text-center max-w-xl mx-auto">
      <div className="relative w-16 h-16 mx-auto mb-5">
        <div className="absolute inset-0 rounded-2xl bg-indigo-500/10 animate-ping" />
        <div className="relative w-16 h-16 rounded-2xl bg-[#EEF2FF] border border-[#CBD5E1] flex items-center justify-center text-[#4F46E5] shadow-sm">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
      </div>

      <h3 className="text-xl font-bold text-[#0F172A] mb-2">
        Multi-Agent Fleet in Progress
      </h3>
      <p className="text-sm text-[#334155] mb-6">
        Executing autonomous 4-agent research pipeline for <span className="font-semibold text-[#4F46E5]">"{topic}"</span> (limit: {limit})
      </p>

      <div className="space-y-3 text-left">
        {PIPELINE_STAGES.map((stage, idx) => (
          <div
            key={stage.key}
            className="flex items-center gap-3 p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0]"
          >
            <div className="w-6 h-6 rounded-full bg-[#EEF2FF] border border-[#CBD5E1] flex items-center justify-center text-[#4F46E5] text-xs font-mono font-bold">
              {idx + 1}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-[#0F172A]">{stage.name}</div>
              <div className="text-xs text-[#64748B] truncate">{stage.action}</div>
            </div>
            <Loader2 className="w-4 h-4 text-[#4F46E5] animate-spin flex-shrink-0" />
          </div>
        ))}
      </div>

      <div className="mt-6 text-xs text-[#64748B] font-mono">
        Authentic live execution against backend <code className="font-mono text-[#334155] bg-slate-100 px-1 py-0.5 rounded border border-[#E2E8F0]">POST /pipeline</code>
      </div>
    </div>
  );
}

