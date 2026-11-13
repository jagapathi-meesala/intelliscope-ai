import React, { useState } from 'react';
import {
  Cpu,
  CheckCircle2,
  XCircle,
  Code2,
  Copy,
  Check,
  Database,
  ShieldCheck,
  Lightbulb,
  BarChart,
  ArrowRight,
  RefreshCw,
  Globe,
  AlertTriangle,
} from 'lucide-react';
import { useResearch } from '../context/ResearchContext';
import AgentStatusBadge from '../components/common/AgentStatusBadge';
import EmptyState from '../components/common/EmptyState';

const AGENT_META = {
  data_collector: {
    name: 'Data Collector Agent',
    icon: Database,
    role: 'Multi-source asynchronous data retrieval (Wikipedia, arXiv, Crossref) & sanitization',
  },
  research_verification: {
    name: 'Research Verification Agent',
    icon: ShieldCheck,
    role: 'Structural integrity, HTTPS enforcement, domain whitelisting, DOI checks & deduplication',
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

const INTEGRATION_BADGE_STYLES = {
  live_tested: 'bg-emerald-950/70 text-emerald-300 border-emerald-600/70',
  implemented: 'bg-cyan-950/70 text-cyan-300 border-cyan-700/60',
  partial: 'bg-amber-950/70 text-amber-300 border-amber-700/60',
  not_integrated: 'bg-slate-900 text-slate-400 border-slate-700',
};

const INTEGRATION_LABELS = {
  live_tested: 'Live Tested',
  implemented: 'Implemented',
  partial: 'Partial',
  not_integrated: 'Not Integrated',
};

function SponsorIntegrationsPanel({ integrationsStatus, probeIntegration }) {
  const [probingId, setProbingId] = useState(null);
  const platforms = integrationsStatus?.platforms
    ? Object.values(integrationsStatus.platforms)
    : [];

  if (platforms.length === 0) {
    return null;
  }

  const handleProbe = async (platformId) => {
    setProbingId(platformId);
    try {
      await probeIntegration?.(platformId);
    } finally {
      setProbingId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <Globe className="w-5 h-5 text-cyan-400" />
            <span>Sponsor Platform Integrations &amp; Interoperability</span>
          </h3>
          <p className="text-xs text-slate-400">
            Live environment inspection from <code className="font-mono text-slate-300">GET /integrations/status</code>. Credentials are never exposed.
          </p>
        </div>
        {integrationsStatus?.summary && (
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
            <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-800/50">
              Live Tested: {integrationsStatus.summary.live_tested ?? 0}
            </span>
            <span className="px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800/50">
              Implemented: {integrationsStatus.summary.implemented ?? 0}
            </span>
            <span className="px-2 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-800/50">
              Partial: {integrationsStatus.summary.partial ?? 0}
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-700">
              Not Integrated: {integrationsStatus.summary.not_integrated ?? 0}
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {platforms.map((item) => {
          const badgeCls =
            INTEGRATION_BADGE_STYLES[item.status] || INTEGRATION_BADGE_STYLES.not_integrated;
          const statusLabel = INTEGRATION_LABELS[item.status] || item.status;

          return (
            <div
              key={item.platform_id}
              className="p-5 rounded-2xl border border-slate-800 bg-navy-900/80 flex flex-col justify-between space-y-3"
            >
              <div className="space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <h4 className="text-sm font-bold text-white">{item.display_name}</h4>
                      <span
                        className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded border ${
                          item.mandatory_for_track
                            ? 'bg-brand-950/60 text-brand-300 border-brand-800/50'
                            : 'bg-slate-900 text-slate-400 border-slate-700'
                        }`}
                      >
                        {item.mandatory_for_track ? 'Mandatory Track' : 'Optional'}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-slate-400">{item.transport_protocol}</span>
                  </div>
                  <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border shrink-0 ${badgeCls}`}>
                    {statusLabel}
                  </span>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed">{item.notes}</p>

                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono bg-navy-950/80 p-2.5 rounded-xl border border-slate-800/80">
                  <div>
                    <span className="text-slate-500 block">Runtime State</span>
                    <span className="text-slate-200">{item.runtime_state}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Credentials</span>
                    <span className={item.credentials_present ? 'text-emerald-400' : 'text-amber-300'}>
                      {item.credentials_present ? 'Configured' : 'Not Configured'}
                    </span>
                  </div>
                </div>

                {item.required_env_vars?.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {item.required_env_vars.map((envVar) => (
                      <span
                        key={envVar}
                        className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-navy-950 text-slate-400 border border-slate-800"
                      >
                        {envVar}
                      </span>
                    ))}
                  </div>
                )}

                {item.last_check_status && (
                  <div className="text-[11px] font-mono text-slate-400 bg-navy-950/60 px-2.5 py-1.5 rounded-lg border border-slate-800/70">
                    Probe: <span className="text-slate-200">{item.last_check_status}</span>
                    {item.last_check_error && (
                      <span className="block text-amber-300/90 mt-0.5 truncate" title={item.last_check_error}>
                        {item.last_check_error}
                      </span>
                    )}
                  </div>
                )}
              </div>

              <div className="pt-2 border-t border-slate-800/70 flex items-center justify-between text-xs">
                <a
                  href={item.official_docs_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand-400 hover:text-brand-300 font-mono text-[11px] underline"
                >
                  Official Docs
                </a>
                <button
                  type="button"
                  onClick={() => handleProbe(item.platform_id)}
                  disabled={probingId === item.platform_id}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-navy-800 hover:bg-slate-800 text-slate-200 border border-slate-700 text-[11px] font-mono transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`w-3 h-3 ${probingId === item.platform_id ? 'animate-spin' : ''}`} />
                  <span>{probingId === item.platform_id ? 'Checking...' : 'Verify Status'}</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function AgentActivity() {
  const { currentPipeline, runsHistory, integrationsStatus, probeIntegration } = useResearch();
  const [copied, setCopied] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);

  if (!currentPipeline && runsHistory.length === 0) {
    return (
      <div className="space-y-8">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight mb-1">Agent Fleet Activity</h2>
          <p className="text-sm text-slate-400">
            Real-time execution telemetry, agent handoffs, and sponsor platform interoperability status.
          </p>
        </div>
        <EmptyState
          title="No Execution Telemetry Logged"
          description="Execute an autonomous multi-agent pipeline to record live agent statuses, step durations, handoffs, and execution details."
          actionText="Execute Research Query"
          actionTo="/new-research"
          icon={Cpu}
        />
        <SponsorIntegrationsPanel
          integrationsStatus={integrationsStatus}
          probeIntegration={probeIntegration}
        />
      </div>
    );
  }

  const pipeline = currentPipeline;
  const statuses = pipeline?.agent_statuses || {};
  const handoffs = pipeline?.handoffs || [];
  const sharedCtx = pipeline?.shared_context;
  const executionId = pipeline?.execution_id || pipeline?.pipeline_id;

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
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-brand-950 text-brand-300 border border-brand-800/40">
              Pipeline Telemetry
            </span>
            {executionId && (
              <span className="text-xs text-slate-400 font-mono">
                Exec ID: {executionId.slice(0, 8)}...
              </span>
            )}
            {sharedCtx?.origin_platform && (
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-navy-900 text-cyan-300 border border-slate-700">
                Origin: {sharedCtx.origin_platform}
              </span>
            )}
            {sharedCtx?.origin_room_id && (
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-navy-900 text-slate-300 border border-slate-700">
                Room: {sharedCtx.origin_room_id}
              </span>
            )}
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
            Execution / Pipeline UUID
          </span>
          <div className="text-xs font-mono text-slate-300 truncate" title={executionId}>
            {executionId || '—'}
          </div>
          <span className="text-[11px] text-emerald-400 font-mono">Shared Context Active</span>
        </div>

        <div>
          <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold block mb-1">
            Handoffs &amp; Agents
          </span>
          <div className="text-2xl font-bold font-mono text-white">
            4 / 4
          </div>
          <span className="text-[11px] text-slate-400 font-mono">
            {handoffs.length} Handoff Checkpoints
          </span>
        </div>
      </div>

      {/* Sequential Execution Breakdown */}
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight">Sequential Agent Execution Timeline</h3>
          <p className="text-xs text-slate-400">
            Ordered pipeline flow with authentic execution status, validation checks, and durations reported by FastAPI.
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

                  <div className="flex flex-wrap items-center gap-3 sm:self-center">
                    {agentStatus?.task_id && (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-navy-950 text-slate-400 border border-slate-800">
                        {agentStatus.task_id}
                      </span>
                    )}
                    {typeof agentStatus?.output_valid === 'boolean' && (
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                          agentStatus.output_valid
                            ? 'bg-emerald-950/50 text-emerald-300 border-emerald-800/50'
                            : 'bg-rose-950/50 text-rose-300 border-rose-800/50'
                        }`}
                      >
                        {agentStatus.output_valid ? 'Schema Valid' : 'Schema Failed'}
                      </span>
                    )}
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

      {/* Agent-to-Agent Handoffs & Provenance Telemetry */}
      {handoffs.length > 0 && (
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-bold text-white tracking-tight">
              Agent Handoffs &amp; Provenance Trace ({handoffs.length})
            </h3>
            <p className="text-xs text-slate-400">
              Validated inter-agent task handoffs carrying execution IDs, source provenance counts, and failure statuses.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-navy-900/80 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-navy-950/80 text-slate-400 border-b border-slate-800 font-medium">
                  <tr>
                    <th className="py-3 px-4">Handoff Route</th>
                    <th className="py-3 px-4">Protocol</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Validation</th>
                    <th className="py-3 px-4">Provenance</th>
                    <th className="py-3 px-4 text-right">Duration</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {handoffs.map((h, idx) => (
                    <tr key={h.handoff_id || idx} className="hover:bg-navy-800/30 transition-colors">
                      <td className="py-3 px-4 font-mono text-white whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5">
                          <span className="text-slate-300">{h.from_agent}</span>
                          <ArrowRight className="w-3 h-3 text-brand-400" />
                          <span className="text-white font-semibold">{h.to_agent}</span>
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-400">{h.protocol}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${
                            h.status === 'completed'
                              ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800/50'
                              : h.status === 'skipped'
                              ? 'bg-slate-900 text-slate-400 border-slate-700'
                              : 'bg-rose-950/60 text-rose-300 border-rose-800/50'
                          }`}
                        >
                          {h.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono">
                        {h.input_validation_passed && h.output_validation_passed ? (
                          <span className="text-emerald-400 inline-flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>In/Out OK</span>
                          </span>
                        ) : h.status === 'skipped' ? (
                          <span className="text-slate-500">—</span>
                        ) : (
                          <span className="text-rose-400 inline-flex items-center gap-1">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            <span>Failed</span>
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono">
                        <span className="text-slate-200">{h.source_provenance_count}</span>
                        {Array.isArray(h.source_providers) && h.source_providers.length > 0 && (
                          <span className="text-slate-500 ml-1.5">
                            ({h.source_providers.join(', ')})
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-300">
                        {(h.duration_ms ?? 0).toFixed(1)} ms
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Sponsor Platform Integrations Panel */}
      <SponsorIntegrationsPanel
        integrationsStatus={integrationsStatus}
        probeIntegration={probeIntegration}
      />

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
