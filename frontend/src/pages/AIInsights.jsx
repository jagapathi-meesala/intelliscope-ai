import React from 'react';
import {
  Lightbulb,
  Layers,
  Tag,
  Quote,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  Compass,
  ShieldAlert,
  Info,
} from 'lucide-react';
import { useResearch } from '../context/ResearchContext';
import { getNormalizedThemes, getSourceDistribution } from '../context/pipelineState';
import SafeExternalLink from '../components/common/SafeExternalLink';
import EmptyState from '../components/common/EmptyState';

export default function AIInsights() {
  const { currentPipeline } = useResearch();

  const analysis = currentPipeline?.analysis;
  const query = currentPipeline?.query || analysis?.topic;

  if (!analysis) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight mb-1">AI Insights & Synthesis</h2>
          <p className="text-sm text-slate-500">
            Explainable, deterministic research synthesis, thematic clustering, and evidence-grounded observations.
          </p>
        </div>
        <EmptyState
          title="No Synthesized Insights Available"
          description="Execute a research query to generate deterministic executive summaries, thematic groupings, and evidence-backed observations."
          actionText="Execute Research Query"
          actionTo="/new-research"
          icon={Lightbulb}
        />
      </div>
    );
  }

  const themes = getNormalizedThemes(analysis);
  const keywords = analysis.important_keywords || [];
  const observations = analysis.evidence_backed_observations || [];
  const gaps = analysis.information_gaps || [];
  const recommendations = analysis.recommendations || [];
  const limitations = analysis.limitations || [];
  const sourceDistEntries = Object.entries(getSourceDistribution(analysis));

  const directlyRelevantCount = currentPipeline?.verification?.directly_relevant_count ?? 0;
  const weaklyRelevantCount = currentPipeline?.verification?.weakly_relevant_count ?? 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 font-medium">
              Insight Analyst Agent
            </span>
            <span className="text-xs text-slate-500 font-mono">
              Deterministic Lexical Clustering
            </span>
          </div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            Intelligence Synthesis: "{query}"
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          {sourceDistEntries.map(([provider, count]) => (
            <span
              key={provider}
              className="px-2.5 py-1 rounded-lg bg-indigo-50/70 border border-indigo-200 text-indigo-900 capitalize"
            >
              {provider}: <strong className="text-indigo-950 font-bold">{count}</strong>
            </span>
          ))}
          <span className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-700 shadow-sm" title="Sources passing HTTPS, domain, and schema verification checks">
            <strong className="text-emerald-600 font-bold">{analysis.eligible_sources_count}</strong> Structurally Eligible
          </span>
          <span className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-700 shadow-sm">
            <strong className="text-emerald-600 font-bold">{directlyRelevantCount}</strong> Direct Relevance
          </span>
          {weaklyRelevantCount > 0 && (
            <span className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-700 shadow-sm">
              <strong className="text-amber-600 font-bold">{weaklyRelevantCount}</strong> Weakly Relevant
            </span>
          )}
          {analysis.excluded_sources_count > 0 && (
            <span className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-700 shadow-sm">
              <strong className="text-rose-600 font-bold">{analysis.excluded_sources_count}</strong> Excluded
            </span>
          )}
        </div>
      </div>

      {/* Executive Summary Card */}
      <div className="p-6 sm:p-8 rounded-2xl border border-[#CBD5E1] bg-[#EEF2FF] shadow-sm">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#4F46E5] mb-3">
          <Quote className="w-4 h-4 text-[#4F46E5]" />
          <span>Executive Summary</span>
        </div>
        <p className="text-base sm:text-lg text-[#0F172A] leading-relaxed font-sans font-normal">
          {analysis.executive_summary}
        </p>
      </div>

      {/* Key Thematic Clusters & Keywords */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Key Themes (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-600" />
              <span>Thematic Clusters ({themes.length})</span>
            </h3>
            <span className="text-xs text-slate-500">Evidence citations (sources may support multiple overlapping themes)</span>
          </div>

          <div className="space-y-3">
            {themes.length === 0 ? (
              <div className="p-4 rounded-xl border border-slate-200 bg-white shadow-sm text-xs text-slate-500 italic">
                No thematic clusters could be derived from the available evidence base.
              </div>
            ) : (
              themes.map((theme, i) => (
                <div
                  key={i}
                  className="p-4 rounded-xl border border-slate-200 bg-white shadow-sm hover:border-slate-300 transition-all space-y-2"
                >
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="text-sm font-bold text-slate-900">{theme.theme}</h4>
                    <span
                      className="text-xs font-mono px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200"
                      title="Evidence citations supporting this theme (individual sources may support multiple overlapping themes)"
                    >
                      {theme.frequency} {theme.frequency === 1 ? 'citation' : 'citations'} (may overlap)
                    </span>
                  </div>

                  <p className="text-xs text-slate-600 leading-relaxed">
                    {theme.description}
                  </p>

                  {theme.sources?.length > 0 && (
                    <div className="pt-1 flex flex-wrap gap-2 text-[11px]">
                      <span className="text-slate-400">Supporting:</span>
                      {theme.sources.map((src, sIdx) => (
                        <SafeExternalLink key={sIdx} href={src} maxLength={35} showIcon={false} />
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Important Keywords Cloud (1 col) */}
        <div className="space-y-4">
          <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Tag className="w-4 h-4 text-cyan-600" />
            <span>Key Terminology</span>
          </h3>

          <div className="p-5 rounded-xl border border-slate-200 bg-white shadow-sm space-y-3">
            <p className="text-xs text-slate-500">
              High-frequency non-stopword tokens extracted deterministically across verified extracts:
            </p>

            <div className="flex flex-wrap gap-2 pt-1">
              {keywords.map((kw, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 rounded-lg bg-slate-100 text-cyan-800 border border-slate-200 font-mono text-xs hover:border-cyan-300 hover:bg-cyan-50/50 transition-colors cursor-default"
                >
                  #{kw}
                </span>
              ))}
              {keywords.length === 0 && (
                <span className="text-xs text-slate-400 italic">No keywords extracted.</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Evidence-Backed Observations */}
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span>Evidence-Backed Observations ({observations.length})</span>
          </h3>
          <p className="text-xs text-slate-500">
            Observations anchored strictly in verified source extracts with dynamic confidence ratings.
          </p>
        </div>

        <div className="space-y-3">
          {observations.length === 0 ? (
            <div className="p-6 rounded-xl border border-slate-200 bg-white shadow-sm text-sm text-slate-500 italic text-center">
              No verified observations could be grounded from the eligible evidence.
            </div>
          ) : (
            observations.map((obs, idx) => {
              const isWeak = Boolean(obs.is_weakly_relevant);
              const rawConf = (obs.confidence || 'high').toLowerCase();
              // Strictly cap weakly relevant sources to low confidence
              const conf = isWeak ? 'low' : rawConf;
              const confStyles = {
                high: 'bg-emerald-50 text-emerald-700 border-emerald-200',
                medium: 'bg-amber-50 text-amber-700 border-amber-200',
                low: 'bg-slate-100 text-slate-600 border-slate-200',
              }[conf] || 'bg-slate-100 text-slate-600 border-slate-200';

              return (
                <div
                  key={idx}
                  className="p-5 rounded-2xl border border-slate-200 bg-white shadow-sm hover:border-slate-300 transition-all space-y-2.5"
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <p className="text-sm font-medium text-slate-800 leading-relaxed flex-1">
                      {obs.statement}
                    </p>

                    <div className="flex items-center gap-2 sm:self-start flex-wrap">
                      {obs.is_weakly_relevant && (
                        <span className="text-xs px-2.5 py-0.5 rounded-full border font-mono font-medium bg-amber-50 text-amber-700 border-amber-200">
                          Weakly Relevant
                        </span>
                      )}
                      <span className={`text-xs px-2.5 py-0.5 rounded-full border font-mono font-medium capitalize ${confStyles}`}>
                        {conf} confidence
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-slate-100 text-xs">
                    <div className="flex flex-wrap items-center gap-1.5 text-slate-500">
                      {obs.source_name && (
                        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                          {obs.source_name}
                        </span>
                      )}
                      {obs.source_type && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                          {obs.source_type}
                        </span>
                      )}
                      <span className="text-slate-400">Source:</span>
                      <span className="font-medium text-slate-900 truncate max-w-xs">{obs.source_title || 'Untitled source'}</span>
                      {obs.source_url && (
                        <>
                          <span>•</span>
                          <SafeExternalLink href={obs.source_url} maxLength={40} />
                        </>
                      )}
                    </div>

                    {obs.confidence_reason && (
                      <div className="flex items-center gap-1 text-slate-500 text-[11px] italic">
                        <Info className="w-3 h-3 text-slate-400 shrink-0" />
                        <span className="truncate max-w-sm">{obs.confidence_reason}</span>
                      </div>
                    )}
                  </div>

                  {(Array.isArray(obs.authors) && obs.authors.length > 0 || obs.publication_date || obs.doi) && (
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500 pt-1">
                      {Array.isArray(obs.authors) && obs.authors.length > 0 && (
                        <span>
                          Authors: <span className="text-slate-700">{obs.authors.slice(0, 3).join(', ')}{obs.authors.length > 3 ? ` +${obs.authors.length - 3}` : ''}</span>
                        </span>
                      )}
                      {obs.publication_date && (
                        <span className="font-mono">
                          Published: <span className="text-slate-700">{obs.publication_date}</span>
                        </span>
                      )}
                      {obs.doi && (
                        <span className="font-mono">
                          DOI: <span className="text-cyan-700">{obs.doi}</span>
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Information Gaps & Recommendations Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Information Gaps */}
        <div className="p-6 rounded-2xl border border-slate-200 bg-white shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-sm font-bold text-amber-700">
            <HelpCircle className="w-4 h-4 text-amber-600" />
            <span>Identified Information Gaps</span>
          </div>
          <p className="text-xs text-slate-500">
            Explicitly disclosed omissions, source attrition, and contextual boundaries:
          </p>
          <ul className="space-y-2 pt-1 text-xs text-slate-700">
            {gaps.map((gap, i) => (
              <li key={i} className="flex items-start gap-2 bg-amber-50/50 p-2.5 rounded-lg border border-amber-100">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
                <span>{gap}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Actionable Recommendations */}
        <div className="p-6 rounded-2xl border border-slate-200 bg-white shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-sm font-bold text-indigo-700">
            <Compass className="w-4 h-4 text-indigo-600" />
            <span>Actionable Next Steps</span>
          </div>
          <p className="text-xs text-slate-500">
            Deterministic research trajectories and query expansion recommendations:
          </p>
          <ul className="space-y-2 pt-1 text-xs text-slate-700">
            {recommendations.map((rec, i) => (
              <li key={i} className="flex items-start gap-2 bg-indigo-50/50 p-2.5 rounded-lg border border-indigo-100">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-600 mt-1.5 flex-shrink-0" />
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Methodological Transparency & Limitations Footer */}
      <div className="p-5 rounded-2xl border border-[#E2E8F0] bg-white shadow-sm space-y-2 text-xs">
        <div className="flex items-center justify-between text-[#64748B] font-semibold border-b border-[#E2E8F0] pb-2">
          <span>Methodology & Epistemic Boundaries</span>
          <span className="text-[#4F46E5] font-mono text-[11px] font-medium">Deterministic Lexical Engine</span>
        </div>
        <p className="text-[#334155] text-xs italic">
          "{analysis.methodology}"
        </p>
        <ul className="list-disc list-inside space-y-1 text-[#64748B] pt-1">
          {limitations.map((lim, i) => (
            <li key={i}>{lim}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

