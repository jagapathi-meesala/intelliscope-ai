import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getNormalizedThemes,
  applyNewRunToState,
  applyBackendHistorySync,
  selectRunInState,
  selectLatestRunInState,
  getOverviewKpis,
  buildHistorySummary,
} from './pipelineState.js';

function makeRun({ id, query, executed_at, sources = 4, eligible = 3, themes = [], status = 'success' }) {
  return {
    pipeline_id: id,
    query,
    status,
    total_duration_ms: 500,
    executed_at,
    summary: `Summary for ${query}`,
    agent_statuses: {},
    research:
      status === 'failed'
        ? null
        : {
            query,
            result_count: sources,
            results: [
              {
                title: `${query} article`,
                snippet: `Substantive extract for ${query}.`,
                source_url: `https://en.wikipedia.org/wiki/${query.replace(/\s+/g, '_')}`,
                relevance: 'relevant',
                is_weakly_relevant: false,
                source_type: 'wikipedia_extract',
              },
            ],
          },
    verification:
      status === 'failed'
        ? null
        : {
            query,
            quality_score: 95.0,
            structurally_valid_count: eligible,
            directly_relevant_count: eligible,
            weakly_relevant_count: 0,
            excluded_count: sources - eligible,
            status: 'passed',
            is_factually_verified: false,
          },
    analysis:
      status === 'failed'
        ? null
        : {
            topic: query,
            eligible_sources_count: eligible,
            excluded_sources_count: sources - eligible,
            executive_summary: `Executive summary for ${query}`,
            key_themes: themes.map((t) => ({
              theme: t.name,
              description: t.description || '',
              frequency: t.count,
              sources: t.sources || [],
            })),
            important_keywords: [query],
            evidence_backed_observations: [
              {
                statement: `Observation for ${query}`,
                source_title: `${query} article`,
                source_url: `https://en.wikipedia.org/wiki/${query.replace(/\s+/g, '_')}`,
                confidence: 'high',
                confidence_reason: 'Substantive extract directly matching query.',
              },
            ],
          },
    dashboard:
      status === 'failed'
        ? null
        : {
            dashboard_id: `dash-${id}`,
            topic: query,
            title: `Research Intelligence Dashboard: ${query}`,
            kpi_cards: [
              { id: 'kpi-total-sources', label: 'Total Sources Evaluated', value: sources },
              { id: 'kpi-theme-count', label: 'Identified Themes', value: themes.length },
            ],
            themes: themes.map((t) => ({
              theme: t.name,
              name: t.name,
              description: t.description || '',
              frequency: t.count,
              evidence_count: t.count,
              sources: t.sources || [],
            })),
            key_themes: themes.map((t) => ({
              theme: t.name,
              name: t.name,
              frequency: t.count,
              evidence_count: t.count,
            })),
            charts: [],
          },
  };
}

test('pipeline response structure matches frontend expectations', () => {
  const sampleResponse = {
    pipeline_id: 'test-uuid-1234',
    query: 'quantum computing',
    status: 'success',
    total_duration_ms: 1245.5,
    executed_at: '2026-03-01T12:00:00Z',
    agent_statuses: {
      data_collector: { agent_name: 'Data Collector Agent', status: 'completed', duration_ms: 300 },
      research_verification: { agent_name: 'Research Verification Agent', status: 'completed', duration_ms: 200 },
      insight_analyst: { agent_name: 'Insight Analyst Agent', status: 'completed', duration_ms: 400 },
      dashboard_builder: { agent_name: 'Dashboard Builder Agent', status: 'completed', duration_ms: 345 },
    },
    research: {
      result_count: 5,
      results: [
        {
          title: 'Quantum computing',
          snippet: 'Quantum computing is a rapidly-emerging technology...',
          source_url: 'https://en.wikipedia.org/wiki/Quantum_computing',
          relevance: 'relevant',
          is_weakly_relevant: false,
          source_type: 'wikipedia_extract',
        },
      ],
    },
    verification: {
      quality_score: 95.0,
      status: 'passed',
      is_factually_verified: false,
      factual_accuracy_disclaimer: 'This verification evaluates structural integrity...',
    },
    analysis: {
      topic: 'quantum computing',
      executive_summary: 'Synthesized research on quantum computing...',
      key_themes: [],
      important_keywords: ['quantum', 'computing'],
      evidence_backed_observations: [],
      information_gaps: [],
      recommendations: [],
    },
    dashboard: {
      title: 'Research Intelligence Dashboard: quantum computing',
      kpi_cards: [],
      charts: [],
    },
  };

  assert.equal(sampleResponse.status, 'success');
  assert.equal(sampleResponse.verification.is_factually_verified, false);
  assert.equal(sampleResponse.research.results[0].relevance, 'relevant');
  assert.equal(sampleResponse.research.results[0].source_type, 'wikipedia_extract');
  assert.equal(sampleResponse.research.results[0].source_url.startsWith('https://'), true);
});

test('Phase 3.4: three themes propagate with names and counts, matching overview KPI', () => {
  const nnRun = makeRun({
    id: 'run-nn',
    query: 'neural networks',
    executed_at: '2026-11-11T10:00:00Z',
    sources: 5,
    eligible: 4,
    themes: [
      { name: 'Architectures', count: 4, sources: ['https://en.wikipedia.org/wiki/Deep_learning'] },
      { name: 'Optimization', count: 3, sources: ['https://en.wikipedia.org/wiki/Backpropagation'] },
      { name: 'Applications', count: 2, sources: ['https://en.wikipedia.org/wiki/Computer_vision'] },
    ],
  });

  const themes = getNormalizedThemes(nnRun.dashboard);
  assert.equal(themes.length, 3);
  assert.equal(themes[0].name, 'Architectures');
  assert.equal(themes[0].evidence_count, 4);
  assert.equal(themes[2].name, 'Applications');
  assert.equal(themes[2].evidence_count, 2);

  const kpis = getOverviewKpis(nnRun, [buildHistorySummary(nnRun)]);
  assert.equal(kpis.totalRuns, 1);
  assert.equal(kpis.sourcesRetrieved, 5);
  assert.equal(kpis.eligibleSources, 4);
  assert.equal(kpis.themeCount, 3);
});

test('Phase 3.4: empty themes handled honestly with count 0', () => {
  const emptyThemesRun = makeRun({
    id: 'run-empty',
    query: 'rare stub',
    executed_at: '2026-11-11T10:05:00Z',
    sources: 1,
    eligible: 1,
    themes: [],
  });

  assert.deepEqual(getNormalizedThemes(emptyThemesRun.dashboard), []);
  assert.equal(getOverviewKpis(emptyThemesRun, [buildHistorySummary(emptyThemesRun)]).themeCount, 0);
});

test('Phase 3.4: latest BAND neural networks run replaces stale quantum overview & history selection restores older run', () => {
  const quantumRun = makeRun({
    id: 'run-quantum',
    query: 'quantum computing',
    executed_at: '2026-11-11T09:00:00Z',
    sources: 5,
    eligible: 5,
    themes: [
      { name: 'Quantum Hardware', count: 3 },
      { name: 'Quantum Algorithms', count: 2 },
    ],
  });

  const nnRun = makeRun({
    id: 'run-nn',
    query: 'neural networks',
    executed_at: '2026-11-11T10:00:00Z',
    sources: 4,
    eligible: 3,
    themes: [
      { name: 'Deep Learning', count: 3 },
      { name: 'Training Methods', count: 2 },
      { name: 'Vision Models', count: 1 },
    ],
  });

  // Initial stale frontend state holds older quantum computing run
  let state = {
    currentPipeline: quantumRun,
    latestSuccessfulRun: quantumRun,
    selectedRunId: null,
    runsHistory: [buildHistorySummary(quantumRun)],
    runDetailsById: { 'run-quantum': quantumRun },
  };

  // Sync backend history containing newer BAND run ('neural networks')
  state = applyBackendHistorySync(state, {
    total_runs: 2,
    latest_successful_pipeline_id: 'run-nn',
    latest_successful_run: nnRun,
    runs: [buildHistorySummary(nnRun), buildHistorySummary(quantumRun)],
  });

  // Active dashboard automatically updates to Neural Networks!
  assert.equal(state.currentPipeline.query, 'neural networks');
  assert.equal(state.runsHistory.length, 2);
  let kpis = getOverviewKpis(state.currentPipeline, state.runsHistory);
  assert.equal(kpis.totalRuns, 2);
  assert.equal(kpis.sourcesRetrieved, 4);
  assert.equal(kpis.eligibleSources, 3);
  assert.equal(kpis.themeCount, 3);

  // Select older Quantum Computing run from history -> restores Quantum sources/insights/dashboard/KPIs
  state = selectRunInState(state, 'run-quantum');
  assert.equal(state.currentPipeline.query, 'quantum computing');
  assert.equal(state.selectedRunId, 'run-quantum');
  assert.equal(state.currentPipeline.research.results[0].title, 'quantum computing article');
  kpis = getOverviewKpis(state.currentPipeline, state.runsHistory);
  assert.equal(kpis.sourcesRetrieved, 5);
  assert.equal(kpis.eligibleSources, 5);
  assert.equal(kpis.themeCount, 2);

  // Return to latest run
  state = selectLatestRunInState(state);
  assert.equal(state.currentPipeline.query, 'neural networks');
  assert.equal(state.selectedRunId, null);
});

test('Phase 3.4: failed research run does not overwrite last successful run', () => {
  const nnRun = makeRun({
    id: 'run-nn',
    query: 'neural networks',
    executed_at: '2026-11-11T10:00:00Z',
    sources: 4,
    eligible: 3,
    themes: [{ name: 'Deep Learning', count: 3 }],
  });

  const failedRun = makeRun({
    id: 'run-fail',
    query: 'timeout query',
    executed_at: '2026-11-11T10:15:00Z',
    status: 'failed',
  });

  let state = {
    currentPipeline: nnRun,
    latestSuccessfulRun: nnRun,
    selectedRunId: null,
    runsHistory: [buildHistorySummary(nnRun)],
    runDetailsById: { 'run-nn': nnRun },
  };

  state = applyNewRunToState(state, failedRun);

  // Failed run is logged in history, but active dashboard preserves neural networks!
  assert.equal(state.runsHistory.length, 2);
  assert.equal(state.runsHistory[0].query, 'timeout query');
  assert.equal(state.runsHistory[0].status, 'failed');
  assert.equal(state.currentPipeline.pipeline_id, 'run-nn');
  assert.equal(state.currentPipeline.query, 'neural networks');
  assert.equal(state.latestSuccessfulRun.pipeline_id, 'run-nn');
});

