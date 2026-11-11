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
    <div className="p-8 rounded-2xl border border-brand-500/20 bg-navy-900/80 backdrop-blur-md my-6 shadow-glow-indigo text-center max-w-xl mx-auto">
      <div className="relative w-16 h-16 mx-auto mb-5">
        <div className="absolute inset-0 rounded-2xl bg-brand-500/20 animate-ping" />
        <div className="relative w-16 h-16 rounded-2xl bg-brand-900/80 border border-brand-500/40 flex items-center justify-center text-brand-400">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
      </div>

      <h3 className="text-xl font-bold text-white mb-2">
        Multi-Agent Fleet in Progress
      </h3>
      <p className="text-sm text-slate-300 mb-6">
        Executing autonomous 4-agent research pipeline for <span className="font-semibold text-brand-300">"{topic}"</span> (limit: {limit})
      </p>

      <div className="space-y-3 text-left">
        {PIPELINE_STAGES.map((stage, idx) => (
          <div
            key={stage.key}
            className="flex items-center gap-3 p-3 rounded-lg bg-navy-950/70 border border-slate-800/80"
          >
            <div className="w-6 h-6 rounded-full bg-brand-950 border border-brand-800 flex items-center justify-center text-brand-400 text-xs font-mono">
              {idx + 1}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-slate-200">{stage.name}</div>
              <div className="text-xs text-slate-400 truncate">{stage.action}</div>
            </div>
            <Loader2 className="w-4 h-4 text-brand-400 animate-spin flex-shrink-0" />
          </div>
        ))}
      </div>

      <div className="mt-6 text-xs text-slate-500">
        Authentic live execution against backend <code className="font-mono text-slate-400">POST /pipeline</code>
      </div>
    </div>
  );
}

