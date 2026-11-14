import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, Clock, Sparkles, AlertCircle, RotateCcw } from 'lucide-react';
import { useResearch } from '../../context/ResearchContext';
import { API_BASE_URL } from '../../api/client';
import AgentStatusBadge from '../common/AgentStatusBadge';

const PAGE_TITLES = {
  '/': 'Platform Overview',
  '/new-research': 'New Autonomous Research',
  '/results': 'Research Results & Sources',
  '/verification': 'Research Verification Audit',
  '/insights': 'AI Insight Synthesis',
  '/dashboard': 'Analytics & Specification Dashboard',
  '/activity': 'Fleet Agent Execution Activity',
};

export default function Header({ onMenuClick }) {
  const location = useLocation();
  const { currentPipeline, isViewingHistoricalRun, selectLatestRun, backendHealth } = useResearch();

  const title = PAGE_TITLES[location.pathname] || 'IntelliScope AI';

  return (
    <header className="sticky top-0 z-30 h-16 bg-navy-900/90 backdrop-blur-md border-b border-slate-800/80 px-4 lg:px-8 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          type="button"
          className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 lg:hidden focus:outline-none"
          aria-label="Toggle navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-base lg:text-lg font-bold text-white tracking-tight">{title}</h1>
          {currentPipeline?.query && (
            <p className="text-xs text-slate-400 hidden sm:block truncate max-w-md">
              Topic: <span className="text-brand-300 font-medium">"{currentPipeline.query}"</span>
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2.5 sm:gap-3">
        {/* Backend offline warning banner */}
        {!backendHealth.healthy && !backendHealth.checking && (
          <span
            className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-950/70 border border-rose-800 text-rose-300 text-xs"
            title={`Backend URL: ${API_BASE_URL}`}
          >
            <AlertCircle className="w-3.5 h-3.5" />
            <span>
              {API_BASE_URL.includes('8010') ? 'Backend Offline (port 8010)' : 'Backend Offline'}
            </span>
          </span>
        )}
        {backendHealth.checking && (
          <span
            className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-950/60 border border-amber-800 text-amber-300 text-xs animate-pulse"
            title={`Connecting to: ${API_BASE_URL}`}
          >
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Connecting to Backend...</span>
          </span>
        )}

        {/* Current status pill */}
        {currentPipeline ? (
          <div className="hidden sm:flex items-center gap-2">
            {isViewingHistoricalRun && (
              <button
                type="button"
                onClick={selectLatestRun}
                title="Switch back to latest research run"
                className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-300 bg-amber-950/60 hover:bg-amber-950 px-2 py-0.5 rounded border border-amber-800/60 transition-colors"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Historical (Latest)</span>
              </button>
            )}
            <AgentStatusBadge status={currentPipeline.status} />
            {currentPipeline.total_duration_ms > 0 && (
              <span className="inline-flex items-center gap-1 text-xs font-mono text-slate-400 bg-navy-950 px-2 py-0.5 rounded border border-slate-800">
                <Clock className="w-3 h-3 text-slate-500" />
                {(currentPipeline.total_duration_ms / 1000).toFixed(2)}s
              </span>
            )}
          </div>
        ) : null}

        {/* Quick Launch CTA */}
        <Link
          to="/new-research"
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-medium text-xs sm:text-sm transition-all shadow-sm shadow-brand-500/25 active:scale-95"
        >
          <Sparkles className="w-4 h-4" />
          <span className="hidden sm:inline">New Research</span>
          <span className="sm:hidden">New</span>
        </Link>
      </div>
    </header>
  );
}

