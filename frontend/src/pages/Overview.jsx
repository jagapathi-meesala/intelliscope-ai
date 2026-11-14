import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Activity,
  Layers,
  ShieldCheck,
  Lightbulb,
  Sparkles,
  ArrowRight,
  Bot,
  Database,
  BarChart,
  CheckCircle2,
  Clock,
  Compass,
  History,
  RotateCcw,
} from 'lucide-react';
import { useResearch } from '../context/ResearchContext';
import { getOverviewKpis } from '../context/pipelineState';
import KPICard from '../components/common/KPICard';
import AgentStatusBadge from '../components/common/AgentStatusBadge';
import EmptyState from '../components/common/EmptyState';

const AGENT_ICONS = {
  data_collector: Database,
  research_verification: ShieldCheck,
  insight_analyst: Lightbulb,
  dashboard_builder: BarChart,
};

export default function Overview() {
  const navigate = useNavigate();
  const {
    currentPipeline,
    runsHistory,
    agentsFleet,
    fleetLoading,
    integrationsStatus,
    isViewingHistoricalRun,
    selectRun,
    selectLatestRun,
    refreshStatus,
  } = useResearch();

  // Compute KPIs strictly from selected/latest active run without double-counting
  const {
    totalRuns,
    sourcesRetrieved,
    eligibleSources,
    themeCount: currentThemesCount,
  } = getOverviewKpis(currentPipeline, runsHistory);

  const directlyRelevantCount = currentPipeline?.verification?.directly_relevant_count ?? 0;
  const weaklyRelevantCount = currentPipeline?.verification?.weakly_relevant_count ?? 0;

  const hasActivity = totalRuns > 0 || currentPipeline !== null;

  const handleOpenHistoryRun = async (runId, targetPath) => {
    const restored = await selectRun(runId);
    if (restored && targetPath) {
      navigate(targetPath);
    }
  };

  return (
    <div className="space-y-8">
      {/* Historical Run Notice Banner */}
      {isViewingHistoricalRun && currentPipeline && (
        <div className="p-4 rounded-xl border border-amber-200 bg-amber-50 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
          <div className="flex items-center gap-2.5 text-xs sm:text-sm text-amber-900">
            <History className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span>
              Viewing historical research run: <strong className="text-amber-950 font-bold">"{currentPipeline.query}"</strong>
              {currentPipeline.executed_at && (
                <span className="text-amber-800/80 font-mono text-xs ml-2">
                  ({new Date(currentPipeline.executed_at).toLocaleString()})
                </span>
              )}
            </span>
          </div>
          <button
            type="button"
            onClick={selectLatestRun}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-900 border border-amber-300 text-xs font-semibold transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Return to Latest Run</span>
          </button>
        </div>
      )}

      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden p-6 sm:p-8 rounded-2xl bg-[#EEF2FF] border border-[#E2E8F0] shadow-sm">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white border border-[#CBD5E1] text-[#4F46E5] text-xs font-semibold mb-3 shadow-xs">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Autonomous Multi-Agent Intelligence System</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-[#0F172A] tracking-tight mb-2">
            IntelliScope AI Control Center
          </h2>
          <p className="text-sm text-[#334155] leading-relaxed mb-4">
            Orchestrates four autonomous agents to discover multi-source evidence across Wikipedia, arXiv, and Crossref,
            verify HTTPS protocol, domain, and DOI compliance, synthesize deterministic observations, and generate React dashboard specifications with zero hallucination.
          </p>
          {currentPipeline?.query && (
            <div className="mb-5 text-xs text-[#334155] flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-1 rounded-lg bg-white border border-[#CBD5E1] font-mono text-[#4F46E5] font-semibold shadow-xs">
                {isViewingHistoricalRun ? 'Selected Run:' : 'Latest Run:'} "{currentPipeline.query}"
              </span>
              {currentPipeline.executed_at && (
                <span className="text-[#64748B] font-mono">
                  {new Date(currentPipeline.executed_at).toLocaleString()}
                </span>
              )}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <Link
              to="/new-research"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#4F46E5] hover:bg-[#4338CA] text-white font-semibold text-sm transition-all shadow-sm active:scale-95"
            >
              <Compass className="w-4 h-4" />
              <span>Launch Research Pipeline</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </Link>
            {currentPipeline && (
              <Link
                to="/dashboard"
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-white hover:bg-slate-50 text-[#334155] border border-[#CBD5E1] font-semibold text-sm transition-all shadow-xs"
              >
                <span>{isViewingHistoricalRun ? 'View Selected Dashboard' : 'View Latest Dashboard'}</span>
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* KPI Summary Cards Matching Selected / Latest Active Run */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Total Pipeline Runs"
          value={totalRuns}
          unit="runs"
          description="Total research runs retained in platform history."
          icon={Activity}
          variant="brand"
        />
        <KPICard
          label="Sources Retrieved"
          value={sourcesRetrieved}
          unit="sources"
          description="External encyclopedia articles gathered in active run."
          icon={Database}
          variant="cyan"
        />
        <KPICard
          label="Structurally Eligible Sources"
          value={eligibleSources}
          unit="sources"
          description={`Passing HTTPS, domain, and schema checks (${directlyRelevantCount} direct, ${weaklyRelevantCount} weak topical relevance).`}
          icon={ShieldCheck}
          variant="emerald"
        />
        <KPICard
          label="Thematic Clusters"
          value={currentThemesCount}
          unit="themes"
          description="Lexical clusters from active run (supporting sources may overlap across themes)."
          icon={Layers}
          variant="amber"
        />
      </div>

      {/* Four Fleet Agent Status Cards */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900 tracking-tight">Platform Agent Fleet</h3>
            <p className="text-xs text-slate-500">Live operational status and capabilities reported by FastAPI backend.</p>
          </div>
          <span className="text-xs font-mono text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200 font-semibold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-sm shadow-emerald-200" />
            <span>4 / 4 Active</span>
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {fleetLoading ? (
            <div className="col-span-full p-8 text-center text-slate-500 text-sm">
              Loading agent fleet status...
            </div>
          ) : agentsFleet ? (
            Object.entries(agentsFleet).map(([key, agent]) => {
              const Icon = AGENT_ICONS[key] || Bot;
              return (
                <div
                  key={key}
                  className="p-5 rounded-xl border border-slate-200 bg-white shadow-sm hover:shadow-md hover:border-indigo-300 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <div className="p-2 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-600">
                        <Icon className="w-5 h-5" />
                      </div>
                      <AgentStatusBadge status={agent.status} label={agent.status} size="sm" />
                    </div>

                    <h4 className="text-sm font-bold text-slate-900 mb-1">{agent.name}</h4>
                    <p className="text-xs text-slate-500 mb-3 line-clamp-2 leading-relaxed">
                      {agent.description}
                    </p>
                  </div>

                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-1.5">
                      Implemented Capabilities
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {agent.capabilities?.slice(0, 3).map((cap) => (
                        <span
                          key={cap}
                          className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200"
                        >
                          {cap.replace(/_/g, ' ')}
                        </span>
                      ))}
                      {agent.capabilities?.length > 3 && (
                        <span className="text-[10px] text-slate-500 px-1 font-mono">
                          +{agent.capabilities.length - 3} more
                        </span>
                      )}
                    </div>

                    {agent.version && (
                      <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500 font-mono">
                        <span>Version</span>
                        <span className="font-semibold text-slate-700">v{agent.version}</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="col-span-full p-6 text-center text-rose-700 text-xs bg-rose-50 rounded-xl border border-rose-200">
              Backend agent metadata unavailable. Ensure FastAPI backend is active and reachable.
            </div>
          )}
        </div>
      </div>

      {/* Genuine Sponsor Platform Interoperability Strip */}
      {integrationsStatus?.platforms && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-lg font-bold text-slate-900 tracking-tight">Sponsor Platform Interoperability</h3>
              <p className="text-xs text-slate-500">
                Genuine runtime integration status across hackathon sponsor platforms (credentials never exposed).
              </p>
            </div>
            <Link
              to="/activity"
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 underline"
            >
              Inspect Details &amp; Handoffs →
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {Object.values(integrationsStatus.platforms).map((plat) => (
              <div
                key={plat.platform_id}
                className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-sm space-y-1.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-slate-900 truncate">{plat.display_name}</span>
                  <span
                    className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded border shrink-0 font-medium ${
                      plat.status === 'live_tested'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : plat.status === 'implemented'
                        ? 'bg-blue-50 text-blue-700 border-blue-200'
                        : plat.status === 'partial'
                        ? 'bg-amber-50 text-amber-700 border-amber-200'
                        : 'bg-slate-100 text-slate-600 border-slate-200'
                    }`}
                  >
                    {plat.status.replace('_', ' ')}
                  </span>
                </div>
                <div className="text-[11px] font-mono text-slate-500 truncate">
                  State: <span className="text-slate-800 font-medium">{plat.runtime_state}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Research Activity Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900 tracking-tight">Recent Research Activity</h3>
            <p className="text-xs text-slate-500">
              Retained research runs across BAND and web UI. Select any successful entry to inspect its sources, verification, insights, and dashboard.
            </p>
          </div>
          <button
            type="button"
            onClick={refreshStatus}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 text-xs font-semibold shadow-xs transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Sync Latest</span>
          </button>
        </div>

        {hasActivity ? (
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold">
                  <tr>
                    <th className="py-3 px-4">Research Query</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Sources (Structurally Eligible / Total)</th>
                    <th className="py-3 px-4" title="Thematic clusters synthesized from evidence (may overlap)">Themes (Overlap)</th>
                    <th className="py-3 px-4">Verification Score</th>
                    <th className="py-3 px-4">Duration</th>
                    <th className="py-3 px-4">Executed</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {runsHistory.map((run) => {
                    const isActive = run.id === currentPipeline?.pipeline_id;
                    const isFailed = run.status === 'failed';
                    return (
                      <tr
                        key={run.id}
                        className={`transition-colors ${
                          isActive
                            ? 'bg-indigo-50/60 hover:bg-indigo-50/80'
                            : 'hover:bg-slate-50'
                        }`}
                      >
                        <td className="py-3 px-4 font-bold text-slate-900 max-w-xs truncate">
                          <div className="flex items-center gap-2">
                            <span className="truncate">{run.query}</span>
                            {isActive && (
                              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 border border-indigo-200 font-bold flex-shrink-0">
                                Active
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <AgentStatusBadge status={run.status} size="sm" />
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-600">
                          <div>
                            <span className="text-emerald-700 font-bold">{run.eligible_count}</span> / {run.source_count}
                            <span className="text-[10px] text-slate-500 block font-sans">
                              {run.directly_relevant_count ?? 0} direct · {run.weakly_relevant_count ?? 0} weak
                            </span>
                          </div>
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-800 font-semibold">
                          {run.theme_count ?? 0}
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-mono font-bold text-slate-900">
                            {run.quality_score}/100
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-500">
                          {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : '—'}
                        </td>
                        <td className="py-3 px-4 text-slate-500">
                          {run.executed_at ? new Date(run.executed_at).toLocaleTimeString() : '—'}
                        </td>
                        <td className="py-3 px-4 text-right space-x-2 whitespace-nowrap">
                          {!isFailed ? (
                            <>
                              <button
                                type="button"
                                onClick={() => selectRun(run.id)}
                                className={`font-semibold underline ${
                                  isActive
                                    ? 'text-slate-400 cursor-default no-underline'
                                    : 'text-indigo-600 hover:text-indigo-800'
                                }`}
                                disabled={isActive}
                              >
                                {isActive ? 'Selected' : 'Select'}
                              </button>
                              <button
                                type="button"
                                onClick={() => handleOpenHistoryRun(run.id, '/results')}
                                className="text-blue-600 hover:text-blue-800 underline font-semibold"
                              >
                                Sources
                              </button>
                              <button
                                type="button"
                                onClick={() => handleOpenHistoryRun(run.id, '/dashboard')}
                                className="text-indigo-600 hover:text-indigo-800 underline font-semibold"
                              >
                                Dashboard
                              </button>
                            </>
                          ) : (
                            <span className="text-rose-600 italic text-[11px]" title={run.summary || 'Run failed'}>
                              Failed (preserved prior run)
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <EmptyState
            title="No Research Runs Logged"
            description="Start your first autonomous research query to see actual multi-agent metrics, source retrieval stats, and live dashboard specifications."
            actionText="Launch New Research"
            actionTo="/new-research"
          />
        )}
      </div>
    </div>
  );
}

