import React from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  Lock,
  Globe,
  Clock,
  Copy,
  Info,
  ShieldAlert,
} from 'lucide-react';
import { useResearch } from '../context/ResearchContext';
import SafeExternalLink from '../components/common/SafeExternalLink';
import AgentStatusBadge from '../components/common/AgentStatusBadge';
import EmptyState from '../components/common/EmptyState';

export default function Verification() {
  const { currentPipeline } = useResearch();

  const verification = currentPipeline?.verification;
  const summary = verification?.summary;
  const items = verification?.results || [];
  const query = currentPipeline?.query;

  if (!verification) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight mb-1">
            Research Verification Audit
          </h2>
          <p className="text-sm text-slate-500">
            Structural integrity, HTTPS enforcement, domain whitelist adherence, and deduplication audit.
          </p>
        </div>
        <EmptyState
          title="No Verification Audit Data"
          description="Execute a research query to view detailed structural scores, per-item check matrices, and provenance diagnostics."
          actionText="Run Research Pipeline"
          actionTo="/new-research"
          icon={ShieldCheck}
        />
      </div>
    );
  }

  const qualityScore = Math.round(verification.quality_score ?? 0);

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 font-medium">
            Research Verification Agent
          </span>
          <span className="text-xs text-slate-500 font-mono">
            {verification.total_results} items evaluated
          </span>
        </div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
          Structural Verification Audit: "{query}"
        </h2>
      </div>

      {/* Mandatory Structural vs. Factual Verification Disclaimer Banner */}
      <div className="p-5 rounded-2xl border border-amber-200 bg-amber-50 text-amber-900 shadow-sm flex items-start gap-4">
        <ShieldAlert className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="text-sm font-bold text-amber-950 flex items-center gap-2">
            <span>Critical Epistemic Boundary: Structural vs. Factual Verification</span>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-100 border border-amber-300 text-amber-800 font-medium">
              is_factually_verified = false
            </span>
          </h4>
          <p className="text-xs sm:text-sm text-amber-800 leading-relaxed">
            {verification.factual_accuracy_disclaimer || (
              "This verification evaluates structural integrity, URL protocol compliance, domain whitelist adherence, " +
              "timestamp validity, and deduplication. It does NOT assert that the factual claims within snippets are verified facts."
            )}
          </p>
          <div className="text-[11px] text-amber-700 font-mono pt-1">
            Structural validity guarantees HTTPS safety and encyclopedia domain whitelisting, but does not substitute for independent empirical fact-checking.
          </div>
        </div>
      </div>

      {/* Quality Score & KPI Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Quality Score Hero Card */}
        <div className="p-6 rounded-2xl border border-slate-200 bg-white shadow-sm flex flex-col justify-between items-center text-center">
          <span className="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">
            Structural Quality Score
          </span>
          <div className="relative my-2">
            <span className="text-5xl font-extrabold font-mono text-slate-900 tracking-tight">
              {qualityScore}
            </span>
            <span className="text-sm font-mono text-slate-400">/100</span>
          </div>
          <AgentStatusBadge status={verification.status} />
        </div>

        {/* Structurally Valid Items KPI */}
        <div className="p-5 rounded-2xl border border-slate-200 bg-white shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase mb-2">
            <span>Structurally Valid</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-3xl font-bold font-mono text-emerald-600 mb-1">
            {verification.structurally_valid_count ?? verification.valid_results_count}
          </div>
          <p className="text-xs text-slate-500">
            Items passing HTTPS, domain, and schema checks ({verification.excluded_count ?? verification.invalid_results_count} excluded).
          </p>
        </div>

        {/* Directly vs Weakly Relevant Breakdown KPI */}
        <div className="p-5 rounded-2xl border border-slate-200 bg-white shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase mb-2">
            <span>Topical Relevance</span>
            <AlertTriangle className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-xl font-bold font-mono text-slate-900 mb-1 flex items-baseline gap-2">
            <span className="text-emerald-600">{verification.directly_relevant_count ?? 0}</span>
            <span className="text-xs text-slate-500 font-normal">direct /</span>
            <span className="text-amber-600">{verification.weakly_relevant_count ?? 0}</span>
            <span className="text-xs text-slate-500 font-normal">weak</span>
          </div>
          <p className="text-xs text-slate-500">Reported separately from structural quality score.</p>
        </div>

        {/* Total Checks Evaluated */}
        <div className="p-5 rounded-2xl border border-slate-200 bg-white shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase mb-2">
            <span>Automated Checks</span>
            <ShieldCheck className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-3xl font-bold font-mono text-slate-900 mb-1">
            {summary?.passed_checks ?? 0}
            <span className="text-sm text-slate-400 font-normal"> / {summary?.total_checks ?? 0}</span>
          </div>
          <p className="text-xs text-slate-500">Total individual structural check rules evaluated.</p>
        </div>
      </div>

      {/* Aggregate Diagnostics Bar */}
      {summary && (
        <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 flex flex-wrap items-center justify-around gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5 text-slate-700">
            <span className="text-slate-500">Excluded:</span>
            <span className={(verification.excluded_count ?? verification.invalid_results_count) > 0 ? 'text-rose-600 font-bold' : 'text-slate-600'}>
              {verification.excluded_count ?? verification.invalid_results_count}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-700">
            <span className="text-slate-500">Directly Relevant:</span>
            <span className="text-emerald-600 font-bold">
              {verification.directly_relevant_count ?? summary.directly_relevant_count ?? 0}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-700">
            <span className="text-slate-500">Weakly Relevant:</span>
            <span className={(verification.weakly_relevant_count ?? 0) > 0 ? 'text-amber-600 font-bold' : 'text-slate-600'}>
              {verification.weakly_relevant_count ?? summary.weakly_relevant_count ?? 0}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-700">
            <span className="text-slate-500">Duplicate URLs:</span>
            <span className={summary.duplicate_urls_count > 0 ? 'text-amber-600 font-bold' : 'text-slate-600'}>
              {summary.duplicate_urls_count}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-700">
            <span className="text-slate-500">Duplicate Titles:</span>
            <span className={summary.duplicate_titles_count > 0 ? 'text-amber-600 font-bold' : 'text-slate-600'}>
              {summary.duplicate_titles_count}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-700">
            <span className="text-slate-500">Warnings / Errors:</span>
            <span className="text-slate-900 font-bold">
              {summary.warning_count} / {summary.error_count}
            </span>
          </div>
        </div>
      )}

      {/* Per-Item Verification Breakdown Cards */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-slate-900 tracking-tight">Per-Source Verification Check Matrix</h3>

        {items.map((item) => (
          <div
            key={item.index}
            className="p-5 sm:p-6 rounded-2xl border border-slate-200 bg-white shadow-sm space-y-4"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                    Item #{item.index + 1}
                  </span>
                  {item.source_name && (
                    <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                      {item.source_name}
                    </span>
                  )}
                  <h4 className="text-base font-bold text-slate-900 truncate max-w-lg">
                    {item.title || 'Untitled Record'}
                  </h4>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                      item.is_weakly_relevant
                        ? 'bg-amber-50 text-amber-700 border-amber-200'
                        : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    }`}
                  >
                    {item.is_weakly_relevant ? 'Weakly Relevant' : 'Directly Relevant'}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <SafeExternalLink href={item.source_url} maxLength={70} />
                  {item.doi && (
                    <span className="text-[11px] font-mono text-cyan-700">DOI: {item.doi}</span>
                  )}
                </div>
                {item.relevance_reason && (
                  <p className="text-[11px] text-slate-500 italic mt-1">{item.relevance_reason}</p>
                )}
              </div>

              <div className="flex items-center gap-3">
                <div className="text-right">
                  <span className="text-[10px] text-slate-400 font-mono block">Item Score</span>
                  <span className="text-sm font-mono font-bold text-slate-900">
                    {Math.round(item.item_score)}/100
                  </span>
                </div>
                <AgentStatusBadge status={item.status} size="sm" />
              </div>
            </div>

            {/* Check Rule Badges */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
              <CheckPill label="Title Valid" valid={item.checks?.title_valid} />
              <CheckPill label="Snippet Valid" valid={item.checks?.snippet_valid} />
              <CheckPill label="HTTPS Protocol" valid={item.checks?.https_valid} />
              <CheckPill label="Allowed Domain" valid={item.checks?.domain_allowed} />
              <CheckPill label="Timestamp" valid={item.checks?.timestamp_valid} />
              <CheckPill label="No URL Dup" valid={!item.checks?.is_duplicate_url} />
              <CheckPill label="No Title Dup" valid={!item.checks?.is_duplicate_title} />
              {item.checks?.doi_valid !== null && item.checks?.doi_valid !== undefined && (
                <CheckPill label="DOI Valid" valid={item.checks.doi_valid && !item.checks.is_duplicate_doi} />
              )}
            </div>

            {/* Warnings or Errors */}
            {(item.warnings?.length > 0 || item.errors?.length > 0) && (
              <div className="space-y-1.5 pt-1">
                {item.warnings?.map((w, i) => (
                  <div key={i} className="text-xs text-amber-800 flex items-center gap-2 bg-amber-50 p-2 rounded-lg border border-amber-200">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                    <span>Warning: {w}</span>
                  </div>
                ))}
                {item.errors?.map((e, i) => (
                  <div key={i} className="text-xs text-rose-800 flex items-center gap-2 bg-rose-50 p-2 rounded-lg border border-rose-200">
                    <XCircle className="w-3.5 h-3.5 text-rose-600 flex-shrink-0" />
                    <span>Error: {e}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function CheckPill({ label, valid }) {
  return (
    <div
      className={`p-2 rounded-lg border text-center flex flex-col items-center justify-center gap-1 ${
        valid
          ? 'bg-emerald-50 border-emerald-200 text-emerald-800 font-medium'
          : 'bg-rose-50 border-rose-200 text-rose-800 font-medium'
      }`}
    >
      <div className="flex items-center gap-1 text-[11px] font-medium truncate">
        {valid ? (
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
        ) : (
          <XCircle className="w-3.5 h-3.5 text-rose-600 flex-shrink-0" />
        )}
        <span className="truncate">{label}</span>
      </div>
    </div>
  );
}

