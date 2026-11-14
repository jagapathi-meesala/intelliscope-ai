import React from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  Calendar,
  Layers,
  BookOpen,
  Search,
  ExternalLink,
  ShieldCheck,
  AlertTriangle,
  Info,
} from 'lucide-react';
import { useResearch } from '../context/ResearchContext';
import SafeExternalLink from '../components/common/SafeExternalLink';
import EmptyState from '../components/common/EmptyState';
import AgentStatusBadge from '../components/common/AgentStatusBadge';

export default function ResearchResults() {
  const { currentPipeline } = useResearch();

  const research = currentPipeline?.research;
  const results = research?.results || [];
  const query = currentPipeline?.query || research?.query;
  const sourceBreakdown = research?.source_breakdown || {};
  const sourceErrors = research?.source_errors || {};

  const directlyRelevantCount =
    currentPipeline?.verification?.directly_relevant_count ??
    results.filter((r) => !r.is_weakly_relevant && r.relevance !== 'weakly_relevant').length;
  const weaklyRelevantCount =
    currentPipeline?.verification?.weakly_relevant_count ??
    results.filter((r) => r.is_weakly_relevant || r.relevance === 'weakly_relevant').length;

  if (!results || results.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight mb-1">Research Sources & Evidence</h2>
          <p className="text-sm text-slate-400">
            Normalized research records retrieved across Wikipedia, arXiv, and Crossref.
          </p>
        </div>
        <EmptyState
          title="No Research Results Found"
          description={
            query
              ? `No verifiable records were found for query "${query}". Try broadening your topic or selecting additional sources.`
              : 'Execute an autonomous research query to populate verified sources and abstracts.'
          }
          actionText="Execute Research Query"
          actionTo="/new-research"
          icon={FileText}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header & Meta */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-brand-950 text-brand-300 border border-brand-800/40">
              Data Collector Agent
            </span>
            <span className="text-xs text-slate-500 font-mono">
              {results.length} {results.length === 1 ? 'record' : 'records'} retrieved
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-800/40">
              {directlyRelevantCount} Directly Relevant
            </span>
            {weaklyRelevantCount > 0 && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-800/40">
                {weaklyRelevantCount} Weakly Relevant
              </span>
            )}
            {Object.entries(sourceBreakdown).map(([src, cnt]) => (
              <span
                key={src}
                className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-navy-950 text-cyan-300 border border-cyan-800/40"
              >
                {src}: {cnt}
              </span>
            ))}
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Research Sources: "{query}"
          </h2>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/verification"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-navy-800 hover:bg-slate-800 text-slate-200 border border-slate-700 text-xs font-medium"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Audit Verification</span>
          </Link>
          <Link
            to="/insights"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-sm"
          >
            <span>AI Insights</span>
          </Link>
        </div>
      </div>

      {/* Partial Source Errors Banner if applicable */}
      {Object.keys(sourceErrors).length > 0 && (
        <div className="p-4 rounded-xl border border-amber-800/60 bg-amber-950/30 text-amber-200 text-xs space-y-1">
          <div className="font-bold flex items-center gap-1.5 text-amber-300">
            <AlertTriangle className="w-4 h-4" />
            <span>Partial Source Provider Notices</span>
          </div>
          {Object.entries(sourceErrors).map(([src, err]) => (
            <p key={src} className="font-mono text-amber-200/90">
              • <strong>{src}:</strong> {err}
            </p>
          ))}
        </div>
      )}

      {/* Results List */}
      <div className="space-y-4">
        {results.map((item, idx) => {
          const isWeak = item.is_weakly_relevant || item.relevance === 'weakly_relevant';
          const sourceName = (item.source_name || 'wikipedia').toLowerCase();
          const provenanceLabel =
            item.source_type === 'wikipedia_extract'
              ? 'page extract'
              : item.source_type === 'wikipedia_search_snippet'
              ? 'search snippet'
              : item.source_type || 'abstract';
          const authorsList = Array.isArray(item.authors) ? item.authors : [];

          return (
            <div
              key={`${item.source_url}-${idx}`}
              className="p-5 sm:p-6 rounded-2xl border border-slate-800 bg-navy-900/80 hover:border-slate-700 transition-all space-y-3"
            >
              {/* Item Header: Title & Badges */}
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2.5 mb-1.5">
                    <span className="w-5 h-5 rounded-full bg-navy-950 border border-slate-800 flex items-center justify-center text-slate-400 font-mono text-xs flex-shrink-0">
                      {idx + 1}
                    </span>
                    <h3 className="text-base sm:text-lg font-bold text-white truncate" title={item.title}>
                      {item.title}
                    </h3>
                  </div>

                  <div className="pl-7 space-y-1">
                    <SafeExternalLink href={item.source_url || item.source} maxLength={75} />
                    {(authorsList.length > 0 || item.publication_date || item.doi) && (
                      <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-400">
                        {authorsList.length > 0 && (
                          <span>
                            <strong className="text-slate-300">Authors:</strong>{' '}
                            {authorsList.slice(0, 4).join(', ')}
                            {authorsList.length > 4 ? ' et al.' : ''}
                          </span>
                        )}
                        {item.publication_date && (
                          <span className="font-mono">
                            <strong className="text-slate-300 font-sans">Published:</strong>{' '}
                            {item.publication_date}
                          </span>
                        )}
                        {item.doi && (
                          <span className="font-mono text-cyan-300">
                            DOI: {item.doi}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Provider, Relevance & Provenance Badges */}
                <div className="flex flex-wrap items-center gap-2 sm:self-start">
                  {/* Provider pill */}
                  <span className="text-[11px] font-mono uppercase px-2 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800/50">
                    {sourceName}
                  </span>

                  {/* Relevance pill */}
                  <span
                    className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border font-medium ${
                      isWeak
                        ? 'bg-amber-950/60 text-amber-300 border-amber-800/80'
                        : 'bg-emerald-950/60 text-emerald-300 border-emerald-800/80'
                    }`}
                    title={item.relevance_reason || 'Relevance determination'}
                  >
                    {isWeak ? (
                      <AlertTriangle className="w-3 h-3 text-amber-400" />
                    ) : (
                      <ShieldCheck className="w-3 h-3 text-emerald-400" />
                    )}
                    <span>{isWeak ? 'Weakly Relevant' : 'Relevant'}</span>
                  </span>

                  {/* Provenance badge */}
                  <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded border bg-cyan-950/50 text-cyan-300 border-cyan-800/50">
                    <BookOpen className="w-3 h-3" />
                    <span>{provenanceLabel}</span>
                  </span>
                </div>
              </div>

              {/* Substantive Extract / Abstract */}
              <div className="pl-7 text-sm text-slate-300 leading-relaxed bg-navy-950/50 p-3.5 rounded-xl border border-slate-800/80">
                {item.abstract || item.snippet}
              </div>

              {/* Relevance Reason & Retrieval Timestamp Footer */}
              <div className="pl-7 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-slate-500 pt-1">
                {item.relevance_reason && (
                  <div className="flex items-center gap-1.5 text-slate-400 italic">
                    <Info className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                    <span className="truncate">{item.relevance_reason}</span>
                  </div>
                )}
                {item.retrieved_at && (
                  <div className="flex items-center gap-1 font-mono text-[11px] text-slate-500 sm:ml-auto">
                    <Calendar className="w-3 h-3" />
                    <span>Retrieved: {new Date(item.retrieved_at).toLocaleString()}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

