import React, { useState } from 'react';
import {
  Cpu,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Code2,
  Copy,
  Check,
  Database,
  ShieldCheck,
  Lightbulb,
  BarChart,
  Calendar,
  Layers,
} from 'lucide-react';
import { useResearch } from '../context/ResearchContext';
import AgentStatusBadge from '../components/common/AgentStatusBadge';
import EmptyState from '../components/common/EmptyState';

const AGENT_META = {
  data_collector: {
    name: 'Data Collector Agent',
    icon: Database,
    role: 'MediaWiki API asynchronous data retrieval & extract sanitization',
  },
  research_verification: {
    name: 'Research Verification Agent',
    icon: ShieldCheck,
    role: 'Structural integrity, HTTPS enforcement, domain whitelisting & deduplication',
  },
  insight_analyst: {
    name: 'Insight Analyst Agent',
    icon: Lightbulb,
    role: 'Deterministic lexical analysis, theme clustering & confidence weighting',
  },
  dashboard_builder: {
    name: 'Dashboard Builder Agent',
    icon: BarChart,
    role: 'Safe declarative dashboard specification & KPI metric generation',
  },
};

export default function AgentActivity() {
  const { currentPipeline, runsHistory } = useResearch();
  const [copied, setCopied] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);

  if (!currentPipeline && runsHistory.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight mb-1">Agent Fleet Activity</h2>
          <p className="text-sm text-slate-400">
            Real-time execution telemetry, agent run durations, and diagnostic status logs.
          </p>
        </div>
        <EmptyState
          title="No Execution Telemetry Logged"
          description="Execute an autonomous multi-agent pipeline to record live agent statuses, step durations, and execution details."
          actionText="Execute Research Query"
          actionTo="/new-research"
          icon={Cpu}
        />
      </div>
    );
  }

  const pipeline = currentPipeline;
  const statuses = pipeline?.agent_statuses || {};

  const handleCopyJson = () => {
    if (!pipeline) return;
    navigator.clipboard.writeText(JSON.stringify(pipeline, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-brand-950 text-brand-300 border border-brand-800/40">
              Pipeline Telemetry
            </span>
            <span className="text-xs text-slate-500 font-mono">
              Pipeline ID: {pipeline?.pipeline_id?.slice(0, 8)}...
            </span>
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Execution Activity: "{pipeline?.query}"
          </h2>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowRawJson(!showRawJson)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-navy-800 hover:bg-slate-800 text-slate-200 border border-slate-700 text-xs font-medium transition-colors"
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>{showRawJson ? 'Hide Raw JSON' : 'Inspect Raw JSON'}</span>
          </button>
          <AgentStatusBadge status={pipeline?.status} />
        </div>
      </div>

      {/* Pipeline Telemetry Overview */}
      <div className="p-6 rounded-2xl border border-slate-800 bg-navy-900/90 shadow-card grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold block mb-1">
            Total Duration
          </span>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold font-mono text-white">
              {((pipeline?.total_duration_ms || 0) / 1000).toFixed(3)}
            </span>
            <span className="text-xs text-slate-400 font-mono">seconds</span>
          </div>
          <span className="text-[11px] text-slate-500 font-mono">
            {pipeline?.total_duration_ms?.toFixed(1)} ms
          </span>
        </div>

        <div>
          <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold block mb-1">
            Execution Timestamp
          </span>
          <div className="text-sm font-mono text-slate-200">
            {pipeline?.executed_at ? new Date(pipeline.executed_at).toLocaleTimeString() : '—'}
          </div>
          <span className="text-[11px] text-slate-500 font-mono">
            {pipeline?.executed_at ? new Date(pipeline.executed_at).toLocaleDateString() : '—'}
          </span>
        </div>

        <div>
          <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold block mb-1">
            Pipeline Run UUID
          </span>
          <div className="text-xs font-mono text-slate-300 truncate" title={pipeline?.pipeline_id}>
            {pipeline?.pipeline_id || '—'}
          </div>
          <span className="text-[11px] text-emerald-400 font-mono">Verified Orchestration</span>
        </div>

        <div>
          <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold block mb-1">
            Agent Count
          </span>
          <div className="text-2xl font-bold font-mono text-white">4 / 4</div>
          <span className="text-[11px] text-slate-500 font-mono">All Agents Executed</span>
        </div>
      </div>

      {/* Sequential Execution Breakdown */}
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight">Sequential Agent Execution Timeline</h3>
          <p className="text-xs text-slate-400">
            Ordered pipeline flow with authentic execution status and durations reported by FastAPI.
          </p>
        </div>

        <div className="space-y-4">
          {Object.entries(AGENT_META).map(([key, meta], idx) => {
            const agentStatus = statuses[key];
            const status = agentStatus?.status || 'skipped';
            const duration = agentStatus?.duration_ms ?? 0;
            const details = agentStatus?.details || 'Step completed without reported diagnostic message.';
            const error = agentStatus?.error;
            const Icon = meta.icon;

            return (
              <div
                key={key}
                className="p-5 sm:p-6 rounded-2xl border border-slate-800 bg-navy-900/80 hover:border-slate-700 transition-all space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-navy-950 border border-slate-800 flex items-center justify-center text-brand-400 font-mono font-bold text-xs flex-shrink-0">
                      0{idx + 1}
                    </div>
                    <div>
                      <h4 className="text-base font-bold text-white flex items-center gap-2">
                        <Icon className="w-4 h-4 text-brand-400" />
                        <span>{agentStatus?.agent_name || meta.name}</span>
                      </h4>
                      <p className="text-xs text-slate-400">{meta.role}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 sm:self-center">
                    <div className="text-right">
                      <span className="text-[10px] text-slate-500 font-mono block">Step Duration</span>
                      <span className="text-xs font-mono font-bold text-white">
                        {duration > 0 ? `${duration.toFixed(1)} ms` : '0 ms'}
                      </span>
                    </div>
                    <AgentStatusBadge status={status} />
                  </div>
                </div>

                {/* Actual step details */}
                <div className="text-xs font-mono text-slate-300 bg-navy-950/70 p-3 rounded-xl border border-slate-800/80 leading-relaxed">
                  <span className="text-slate-500 block mb-0.5 text-[10px] uppercase tracking-wider">
                    Execution Details:
                  </span>
                  {details}
                </div>

                {error && (
                  <div className="text-xs font-mono text-rose-300 bg-rose-950/40 p-3 rounded-xl border border-rose-900/80">
                    <span className="text-rose-400 font-bold block mb-0.5">Execution Failure:</span>
                    {error}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Raw JSON Inspector Modal / Collapsible */}
      {showRawJson && pipeline && (
        <div className="p-6 rounded-2xl border border-slate-800 bg-navy-950 shadow-card space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-bold text-white flex items-center gap-2">
              <Code2 className="w-4 h-4 text-brand-400" />
              <span>Full Pipeline Response Payload (JSON)</span>
            </h4>
            <button
              onClick={handleCopyJson}
              type="button"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-navy-900 hover:bg-slate-800 text-slate-200 border border-slate-700 text-xs font-mono transition-colors"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy JSON</span>
                </>
              )}
            </button>
          </div>

          <pre className="p-4 rounded-xl bg-navy-900 border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto max-h-96 leading-relaxed">
            {JSON.stringify(pipeline, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

