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
          <h2 className="text-2xl font-bold text-white tracking-tight mb-1">AI Insights & Synthesis</h2>
          <p className="text-sm text-slate-400">
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-brand-950 text-brand-300 border border-brand-800/40">
              Insight Analyst Agent
            </span>
            <span className="text-xs text-slate-500 font-mono">
              Deterministic Lexical Clustering
            </span>
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Intelligence Synthesis: "{query}"
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          {sourceDistEntries.map(([provider, count]) => (
            <span
              key={provider}
              className="px-2.5 py-1 rounded-lg bg-brand-950/60 border border-brand-800/40 text-brand-200 capitalize"
            >
              {provider}: <strong className="text-white font-bold">{count}</strong>
            </span>
          ))}
          <span className="px-2.5 py-1 rounded-lg bg-navy-900 border border-slate-800 text-slate-300" title="Sources passing HTTPS, domain, and schema verification checks">
            <strong className="text-emerald-400 font-bold">{analysis.eligible_sources_count}</strong> Structurally Eligible
          </span>
          <span className="px-2.5 py-1 rounded-lg bg-navy-900 border border-slate-800 text-slate-300">
            <strong className="text-emerald-400 font-bold">{directlyRelevantCount}</strong> Direct Relevance
          </span>
          {weaklyRelevantCount > 0 && (
            <span className="px-2.5 py-1 rounded-lg bg-navy-900 border border-slate-800 text-slate-400">
              <strong className="text-amber-400 font-bold">{weaklyRelevantCount}</strong> Weakly Relevant
            </span>
          )}
          {analysis.excluded_sources_count > 0 && (
            <span className="px-2.5 py-1 rounded-lg bg-navy-900 border border-slate-800 text-slate-400">
              <strong className="text-rose-400 font-bold">{analysis.excluded_sources_count}</strong> Excluded
            </span>
          )}
        </div>
      </div>

      {/* Executive Summary Card */}
      <div className="p-6 sm:p-8 rounded-2xl border border-brand-500/20 bg-gradient-to-br from-navy-900 via-navy-900 to-navy-850 shadow-glow-indigo">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-400 mb-3">
          <Quote className="w-4 h-4" />
          <span>Executive Summary</span>
        </div>
        <p className="text-base sm:text-lg text-slate-100 leading-relaxed font-sans font-normal">
          {analysis.executive_summary}
        </p>
      </div>

      {/* Key Thematic Clusters & Keywords */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Key Themes (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-brand-400" />
              <span>Thematic Clusters ({themes.length})</span>
            </h3>
            <span className="text-xs text-slate-400">Evidence citations (sources may support multiple overlapping themes)</span>
          </div>

          <div className="space-y-3">
            {themes.length === 0 ? (
              <div className="p-4 rounded-xl border border-slate-800 bg-navy-900 text-xs text-slate-400 italic">
                No thematic clusters could be derived from the available evidence base.
              </div>
            ) : (
              themes.map((theme, i) => (
                <div
                  key={i}
                  className="p-4 rounded-xl border border-slate-800 bg-navy-900/80 hover:border-slate-700 transition-all space-y-2"
                >
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="text-sm font-bold text-white">{theme.theme}</h4>
                    <span
                      className="text-xs font-mono px-2 py-0.5 rounded-full bg-navy-950 text-brand-300 border border-brand-800/40"
                      title="Evidence citations supporting this theme (individual sources may support multiple overlapping themes)"
                    >
                      {theme.frequency} {theme.frequency === 1 ? 'citation' : 'citations'} (may overlap)
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed">
                    {theme.description}
                  </p>

                  {theme.sources?.length > 0 && (
                    <div className="pt-1 flex flex-wrap gap-2 text-[11px]">
                      <span className="text-slate-500">Supporting:</span>
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
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <Tag className="w-4 h-4 text-cyan-400" />
            <span>Key Terminology</span>
          </h3>

          <div className="p-5 rounded-xl border border-slate-800 bg-navy-900/80 space-y-3">
            <p className="text-xs text-slate-400">
              High-frequency non-stopword tokens extracted deterministically across verified extracts:
            </p>

            <div className="flex flex-wrap gap-2 pt-1">
              {keywords.map((kw, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 rounded-lg bg-navy-950 text-cyan-300 border border-cyan-800/40 font-mono text-xs hover:border-cyan-500 transition-colors cursor-default"
                >
                  #{kw}
                </span>
              ))}
              {keywords.length === 0 && (
                <span className="text-xs text-slate-500 italic">No keywords extracted.</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Evidence-Backed Observations */}
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            <span>Evidence-Backed Observations ({observations.length})</span>
          </h3>
          <p className="text-xs text-slate-400">
            Observations anchored strictly in verified source extracts with dynamic confidence ratings.
          </p>
        </div>

        <div className="space-y-3">
          {observations.length === 0 ? (
            <div className="p-6 rounded-xl border border-slate-800 bg-navy-900 text-sm text-slate-400 italic text-center">
              No verified observations could be grounded from the eligible evidence.
            </div>
          ) : (
            observations.map((obs, idx) => {
              const isWeak = Boolean(obs.is_weakly_relevant);
              const rawConf = (obs.confidence || 'high').toLowerCase();
              // Strictly cap weakly relevant sources to low confidence
              const conf = isWeak ? 'low' : rawConf;
              const confStyles = {
                high: 'bg-emerald-950/60 text-emerald-300 border-emerald-800',
                medium: 'bg-amber-950/60 text-amber-300 border-amber-800',
                low: 'bg-slate-800 text-slate-300 border-slate-700',
              }[conf] || 'bg-slate-800 text-slate-300 border-slate-700';

              return (
                <div
                  key={idx}
                  className="p-5 rounded-2xl border border-slate-800 bg-navy-900/80 hover:border-slate-700 transition-all space-y-2.5"
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <p className="text-sm font-medium text-slate-100 leading-relaxed flex-1">
                      {obs.statement}
                    </p>

                    <div className="flex items-center gap-2 sm:self-start flex-wrap">
                      {obs.is_weakly_relevant && (
                        <span className="text-xs px-2.5 py-0.5 rounded-full border font-mono font-medium bg-amber-950/60 text-amber-300 border-amber-800">
                          Weakly Relevant
                        </span>
                      )}
                      <span className={`text-xs px-2.5 py-0.5 rounded-full border font-mono font-medium capitalize ${confStyles}`}>
                        {conf} confidence
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-slate-800/80 text-xs">
                    <div className="flex flex-wrap items-center gap-1.5 text-slate-400">
                      {obs.source_name && (
                        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-brand-950/60 text-brand-300 border border-brand-800/40">
                          {obs.source_name}
                        </span>
                      )}
                      {obs.source_type && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-navy-950 text-slate-400 border border-slate-800">
                          {obs.source_type}
                        </span>
                      )}
                      <span className="text-slate-500">Source:</span>
                      <span className="font-medium text-white truncate max-w-xs">{obs.source_title || 'Untitled source'}</span>
                      {obs.source_url && (
                        <>
                          <span>•</span>
                          <SafeExternalLink href={obs.source_url} maxLength={40} />
                        </>
                      )}
                    </div>

                    {obs.confidence_reason && (
                      <div className="flex items-center gap-1 text-slate-400 text-[11px] italic">
                        <Info className="w-3 h-3 text-slate-500 shrink-0" />
                        <span className="truncate max-w-sm">{obs.confidence_reason}</span>
                      </div>
                    )}
                  </div>

                  {(Array.isArray(obs.authors) && obs.authors.length > 0 || obs.publication_date || obs.doi) && (
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-400 pt-1">
                      {Array.isArray(obs.authors) && obs.authors.length > 0 && (
                        <span>
                          Authors: <span className="text-slate-300">{obs.authors.slice(0, 3).join(', ')}{obs.authors.length > 3 ? ` +${obs.authors.length - 3}` : ''}</span>
                        </span>
                      )}
                      {obs.publication_date && (
                        <span className="font-mono">
                          Published: <span className="text-slate-300">{obs.publication_date}</span>
                        </span>
                      )}
                      {obs.doi && (
                        <span className="font-mono">
                          DOI: <span className="text-cyan-300">{obs.doi}</span>
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
        <div className="p-6 rounded-2xl border border-slate-800 bg-navy-900/80 space-y-3">
          <div className="flex items-center gap-2 text-sm font-bold text-amber-400">
            <HelpCircle className="w-4 h-4" />
            <span>Identified Information Gaps</span>
          </div>
          <p className="text-xs text-slate-400">
            Explicitly disclosed omissions, source attrition, and contextual boundaries:
          </p>
          <ul className="space-y-2 pt-1 text-xs text-slate-300">
            {gaps.map((gap, i) => (
              <li key={i} className="flex items-start gap-2 bg-navy-950/60 p-2.5 rounded-lg border border-slate-800">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 flex-shrink-0" />
                <span>{gap}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Actionable Recommendations */}
        <div className="p-6 rounded-2xl border border-slate-800 bg-navy-900/80 space-y-3">
          <div className="flex items-center gap-2 text-sm font-bold text-brand-400">
            <Compass className="w-4 h-4" />
            <span>Actionable Next Steps</span>
          </div>
          <p className="text-xs text-slate-400">
            Deterministic research trajectories and query expansion recommendations:
          </p>
          <ul className="space-y-2 pt-1 text-xs text-slate-300">
            {recommendations.map((rec, i) => (
              <li key={i} className="flex items-start gap-2 bg-navy-950/60 p-2.5 rounded-lg border border-slate-800">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-400 mt-1.5 flex-shrink-0" />
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Methodological Transparency & Limitations Footer */}
      <div className="p-5 rounded-2xl border border-slate-800 bg-navy-950/70 space-y-2 text-xs">
        <div className="flex items-center justify-between text-slate-400 font-semibold border-b border-slate-800 pb-2">
          <span>Methodology & Epistemic Boundaries</span>
          <span className="text-brand-400 font-mono text-[11px]">Deterministic Lexical Engine</span>
        </div>
        <p className="text-slate-300 text-xs italic">
          "{analysis.methodology}"
        </p>
        <ul className="list-disc list-inside space-y-1 text-slate-400 pt-1">
          {limitations.map((lim, i) => (
            <li key={i}>{lim}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

