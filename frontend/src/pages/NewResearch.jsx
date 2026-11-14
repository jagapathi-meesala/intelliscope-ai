import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Compass,
  Sparkles,
  Sliders,
  Play,
  ArrowRight,
  Database,
  ShieldCheck,
  Lightbulb,
  BarChart,
  CheckCircle2,
  Clock,
  AlertCircle,
  RotateCcw,
} from 'lucide-react';
import { useResearch } from '../context/ResearchContext';
import { API_BASE_URL } from '../api/client';
import LoadingState from '../components/common/LoadingState';
import ErrorAlert from '../components/common/ErrorAlert';
import AgentStatusBadge from '../components/common/AgentStatusBadge';

const RESEARCH_PROVIDERS = [
  {
    id: 'wikipedia',
    name: 'Wikipedia',
    description: 'Encyclopedia articles & introductory page extracts',
    domain: 'en.wikipedia.org',
  },
  {
    id: 'arxiv',
    name: 'arXiv',
    description: 'Open-access academic papers & preprints (Atom XML API)',
    domain: 'arxiv.org',
  },
  {
    id: 'crossref',
    name: 'Crossref',
    description: 'Scholarly publication metadata, DOIs & abstracts',
    domain: 'api.crossref.org',
  },
];

const SUGGESTIONS = [
  'Quantum computing',
  'Neural architecture search',
  'Natural language processing',
  'Autonomous vehicles',
  'Reinforcement learning',
  'CRISPR gene editing',
];

const AGENT_ORDER = [
  { key: 'data_collector', name: 'Data Collector Agent', icon: Database },
  { key: 'research_verification', name: 'Research Verification Agent', icon: ShieldCheck },
  { key: 'insight_analyst', name: 'Insight Analyst Agent', icon: Lightbulb },
  { key: 'dashboard_builder', name: 'Dashboard Builder Agent', icon: BarChart },
];

export default function NewResearch() {
  const { currentPipeline, isExecuting, executionError, startResearch, backendHealth } = useResearch();

  const [topic, setTopic] = useState('');
  const [limit, setLimit] = useState(5);
  const [selectedSources, setSelectedSources] = useState(['wikipedia']);

  const toggleSource = (srcId) => {
    setSelectedSources((prev) => {
      if (prev.includes(srcId)) {
        // Keep at least one selected source or allow unchecking then show validation hint
        return prev.filter((id) => id !== srcId);
      }
      return [...prev, srcId];
    });
  };

  const selectAllSources = () => {
    setSelectedSources(RESEARCH_PROVIDERS.map((p) => p.id));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!topic.trim() || selectedSources.length === 0 || isExecuting) return;

    try {
      await startResearch(topic, limit, selectedSources);
    } catch {
      // Error handled by context while preserving prior successful run
    }
  };

  const handleSuggestionClick = (query) => {
    setTopic(query);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight mb-1">
          Initiate Autonomous Multi-Agent Research
        </h2>
        <p className="text-sm text-slate-500">
          Submits a research topic to the unified FastAPI pipeline. Results pass through all 4 agents deterministically.
        </p>
      </div>

      {/* Research Query Input Form */}
      <div className="p-6 sm:p-8 rounded-2xl border border-slate-200 bg-white shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Topic Input */}
          <div>
            <label htmlFor="topic-input" className="block text-sm font-semibold text-slate-800 mb-2">
              Research Topic or Query
            </label>
            <div className="relative">
              <input
                id="topic-input"
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g., Quantum computing, Deep reinforcement learning, Generative AI..."
                maxLength={300}
                required
                disabled={isExecuting}
                className="w-full px-4 py-3.5 rounded-xl bg-white border border-[#CBD5E1] text-[#0F172A] placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#4F46E5] focus:border-transparent text-sm transition-all"
              />
              <div className="absolute right-3 top-3.5 text-xs font-mono text-slate-400">
                {topic.length}/300
              </div>
            </div>
          </div>

          {/* Result Limit Slider */}
          <div>
            <div className="flex items-center justify-between text-sm mb-2">
              <label htmlFor="limit-slider" className="font-semibold text-slate-800 flex items-center gap-1.5">
                <Sliders className="w-4 h-4 text-indigo-600" />
                <span>Result Limit (Per Selected Source)</span>
              </label>
              <span className="font-mono font-bold text-indigo-700 bg-indigo-50 px-2.5 py-0.5 rounded border border-indigo-200">
                {limit} {limit === 1 ? 'source' : 'sources'} / provider
              </span>
            </div>
            <input
              id="limit-slider"
              type="range"
              min={1}
              max={10}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              disabled={isExecuting}
              className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
            />
            <div className="flex justify-between text-[11px] text-slate-400 font-mono mt-1">
              <span>Min: 1</span>
              <span>Default: 5</span>
              <span>Max: 10</span>
            </div>
          </div>

          {/* Multi-Source Provider Selection */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-slate-800 flex items-center gap-1.5">
                <Database className="w-4 h-4 text-indigo-600" />
                <span>Research Sources ({selectedSources.length} selected)</span>
              </span>
              <button
                type="button"
                disabled={isExecuting}
                onClick={selectAllSources}
                className="text-xs text-indigo-600 hover:text-indigo-800 underline font-semibold"
              >
                Select All Sources
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {RESEARCH_PROVIDERS.map((provider) => {
                const checked = selectedSources.includes(provider.id);
                return (
                  <label
                    key={provider.id}
                    className={`cursor-pointer p-3.5 rounded-xl border transition-all flex flex-col justify-between gap-2 ${
                      checked
                        ? 'bg-[#EEF2FF] border-[#4F46E5] shadow-sm'
                        : 'bg-white border-[#E2E8F0] hover:border-[#CBD5E1]'
                    } ${isExecuting ? 'opacity-60 cursor-not-allowed' : ''}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-bold text-[#0F172A]">{provider.name}</span>
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={isExecuting}
                        onChange={() => toggleSource(provider.id)}
                        className="w-4 h-4 accent-[#4F46E5] rounded"
                      />
                    </div>
                    <p className="text-[11px] text-[#64748B] leading-snug">{provider.description}</p>
                    <span className="text-[10px] font-mono text-[#64748B]">{provider.domain}</span>
                  </label>
                );
              })}
            </div>

            {selectedSources.length === 0 && (
              <p className="mt-2 text-xs text-rose-600 font-medium">
                Select at least one research provider before launching the pipeline.
              </p>
            )}
          </div>

          {/* Suggested Topics */}
          <div>
            <div className="text-xs font-semibold text-[#64748B] mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-[#4F46E5]" />
              <span>Suggested Research Topics</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((sug) => (
                <button
                  key={sug}
                  type="button"
                  disabled={isExecuting}
                  onClick={() => handleSuggestionClick(sug)}
                  className="text-xs px-3 py-1.5 rounded-lg bg-white hover:bg-slate-100 text-[#334155] hover:text-[#0F172A] border border-[#CBD5E1] font-medium transition-colors shadow-xs"
                >
                  {sug}
                </button>
              ))}
            </div>
          </div>

          {/* Backend Health Alert Notice */}
          {!backendHealth?.healthy && !backendHealth?.checking && (
            <div className="p-3.5 rounded-xl border border-rose-200 bg-rose-50 text-xs text-rose-800 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>
                FastAPI backend is currently offline or waking from sleep. Research requests will be enabled once the server responds at{' '}
                <code className="font-mono text-rose-900 font-semibold">{API_BASE_URL}</code>.
              </span>
            </div>
          )}

          {/* Submit Action */}
          <div className="pt-2 flex items-center justify-between gap-4 border-t border-[#E2E8F0]">
            <div className="text-xs text-[#64748B] font-mono">
              Endpoint: <code className="font-mono text-[#334155] bg-slate-100 px-1 py-0.5 rounded border border-[#E2E8F0]">POST /pipeline</code>
            </div>

            <button
              type="submit"
              disabled={
                !topic.trim() ||
                selectedSources.length === 0 ||
                isExecuting ||
                (!backendHealth?.healthy && !backendHealth?.checking) ||
                backendHealth?.checking
              }
              title={
                !backendHealth?.healthy && !backendHealth?.checking
                  ? `Backend is offline at ${API_BASE_URL}`
                  : backendHealth?.checking
                  ? 'Connecting to backend...'
                  : !topic.trim()
                  ? 'Enter a research topic or select a suggestion to begin'
                  : selectedSources.length === 0
                  ? 'Select at least one research source'
                  : 'Execute autonomous multi-agent pipeline'
              }
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#4F46E5] hover:bg-[#4338CA] disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm transition-all shadow-sm active:scale-95"
            >
              <Play className="w-4 h-4 fill-current" />
              <span>
                {isExecuting
                  ? 'Executing Fleet...'
                  : backendHealth?.checking
                  ? 'Connecting...'
                  : !backendHealth?.healthy && !backendHealth?.checking
                  ? 'Backend Offline'
                  : 'Start Research'}
              </span>
            </button>
          </div>
        </form>
      </div>

      {/* Live Loading Display */}
      {isExecuting && <LoadingState topic={topic} limit={limit} />}

      {/* Error Alert Display */}
      {executionError && (
        <ErrorAlert
          error={executionError}
          onRetry={handleSubmit}
          title="Pipeline Execution Failed"
        />
      )}

      {/* Real-time Agent Execution Breakdown (Once Executed) */}
      {currentPipeline && !isExecuting && (
        <div className="p-6 rounded-2xl border border-slate-200 bg-white shadow-sm space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider">
                  Active Execution Breakdown
                </span>
                <AgentStatusBadge status={currentPipeline.status} size="sm" />
              </div>
              <h3 className="text-lg font-bold text-slate-900">
                "{currentPipeline.query}"
              </h3>
              {currentPipeline.research?.sources_requested && (
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {currentPipeline.research.sources_requested.map((src) => (
                    <span
                      key={src}
                      className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 font-semibold"
                    >
                      {src}: {currentPipeline.research?.source_breakdown?.[src] ?? 0}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="text-right">
              <span className="text-xs text-slate-500 font-mono block">Total Fleet Duration</span>
              <span className="text-sm font-mono font-bold text-slate-900">
                {((currentPipeline.total_duration_ms || 0) / 1000).toFixed(2)}s
              </span>
            </div>
          </div>

          {/* Actual 4-Agent Execution Cards - Never simulated */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {AGENT_ORDER.map(({ key, name, icon: Icon }) => {
              const agentStatus = currentPipeline?.agent_statuses?.[key];
              const status = agentStatus?.status || 'skipped';
              const duration = agentStatus?.duration_ms ?? 0;
              const details = agentStatus?.details || 'No execution details reported.';
              const error = agentStatus?.error;

              return (
                <div
                  key={key}
                  className="p-4 rounded-xl border border-[#E2E8F0] bg-white flex flex-col justify-between shadow-xs"
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-lg bg-[#EEF2FF] border border-[#E2E8F0] text-[#4F46E5] shadow-xs">
                        <Icon className="w-4 h-4" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-[#0F172A]">{name}</h4>
                        <div className="text-[11px] font-mono text-[#64748B]">
                          {duration > 0 ? `${(duration / 1000).toFixed(3)}s` : '0.000s'}
                        </div>
                      </div>
                    </div>
                    <AgentStatusBadge status={status} size="sm" />
                  </div>

                  <p className="text-xs text-[#334155] mt-2 font-mono bg-[#F8FAFC] p-2.5 rounded-lg border border-[#E2E8F0] leading-relaxed">
                    {details}
                  </p>

                  {error && (
                    <p className="text-xs text-rose-700 mt-2 font-mono bg-rose-50 p-2.5 rounded-lg border border-rose-200">
                      Error: {error}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {/* Quick Navigation into Specialized Views */}
          <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-[#E2E8F0]">
            <span className="text-xs text-[#64748B]">
              Pipeline run complete. Explore synthesized insights:
            </span>
            <div className="flex flex-wrap gap-2">
              <Link
                to="/results"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-[#334155] text-xs font-semibold border border-[#CBD5E1] shadow-xs"
              >
                <span>Sources ({currentPipeline?.research?.result_count || 0})</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
              <Link
                to="/verification"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-[#334155] text-xs font-semibold border border-[#CBD5E1] shadow-xs"
              >
                <span>Verification Audit</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
              <Link
                to="/insights"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-[#334155] text-xs font-semibold border border-[#CBD5E1] shadow-xs"
              >
                <span>AI Insights</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
              <Link
                to="/dashboard"
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#4F46E5] hover:bg-[#4338CA] text-white text-xs font-semibold shadow-sm"
              >
                <span>View Dashboard</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

