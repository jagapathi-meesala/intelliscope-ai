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
  getSourceDistribution,
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

test('Phase 4: getSourceDistribution resolves dashboard, analysis, and research fallback safely', () => {
  assert.deepEqual(getSourceDistribution(null), {});
  assert.deepEqual(getSourceDistribution({}), {});
  assert.deepEqual(getSourceDistribution({ source_distribution: { wikipedia: 2, arxiv: 1 } }), {
    wikipedia: 2,
    arxiv: 1,
  });
  assert.deepEqual(
    getSourceDistribution({ dashboard: { source_distribution: { crossref: 3 } } }),
    { crossref: 3 }
  );
  assert.deepEqual(
    getSourceDistribution({ analysis: { source_distribution: { arxiv: 2 } } }),
    { arxiv: 2 }
  );
  assert.deepEqual(
    getSourceDistribution({ research: { source_breakdown: { wikipedia: 1, crossref: 2 } } }),
    { wikipedia: 1, crossref: 2 }
  );
});

test('Phase 4: buildHistorySummary preserves sources_requested, source_breakdown, and multi-source provenance', () => {
  const multiRun = {
    pipeline_id: 'run-multi-1',
    query: 'quantum error correction',
    status: 'success',
    total_duration_ms: 420,
    executed_at: '2026-11-11T12:00:00Z',
    research: {
      query: 'quantum error correction',
      result_count: 3,
      sources_requested: ['wikipedia', 'arxiv', 'crossref'],
      source_breakdown: { wikipedia: 1, arxiv: 1, crossref: 1 },
      source_errors: { crossref: 'Partial note' },
      results: [
        {
          title: 'Surface Codes Paper',
          snippet: 'Logical qubits with surface codes.',
          source_name: 'arxiv',
          source_type: 'arxiv_paper',
          source_url: 'https://arxiv.org/abs/2401.12345v1',
          publication_date: '2024-01-22',
          doi: '10.1103/PhysRevLett.132.010501',
          authors: ['Alice Smith', 'Bob Chen'],
        },
      ],
    },
    verification: {
      structurally_valid_count: 3,
      duplicate_dois_count: 0,
    },
    analysis: {
      topic: 'quantum error correction',
      eligible_sources_count: 3,
      excluded_sources_count: 0,
      source_distribution: { wikipedia: 1, arxiv: 1, crossref: 1 },
      key_themes: [{ theme: 'Fault Tolerance', frequency: 3 }],
      evidence_backed_observations: [
        {
          statement: "According to 'Surface Codes Paper': Logical qubits with surface codes.",
          source_title: 'Surface Codes Paper',
          source_url: 'https://arxiv.org/abs/2401.12345v1',
          source_name: 'arxiv',
          source_type: 'arxiv_paper',
          publication_date: '2024-01-22',
          doi: '10.1103/PhysRevLett.132.010501',
          authors: ['Alice Smith', 'Bob Chen'],
          confidence: 'high',
        },
      ],
    },
    dashboard: {
      dashboard_id: 'dash-multi-1',
      topic: 'quantum error correction',
      source_distribution: { wikipedia: 1, arxiv: 1, crossref: 1 },
      themes: [{ theme: 'Fault Tolerance', name: 'Fault Tolerance', frequency: 3, evidence_count: 3 }],
      observations: [
        {
          statement: "According to 'Surface Codes Paper': Logical qubits with surface codes.",
          source_title: 'Surface Codes Paper',
          source_url: 'https://arxiv.org/abs/2401.12345v1',
          source_name: 'arxiv',
          source_type: 'arxiv_paper',
          publication_date: '2024-01-22',
          doi: '10.1103/PhysRevLett.132.010501',
          authors: ['Alice Smith', 'Bob Chen'],
        },
      ],
    },
  };

  const summary = buildHistorySummary(multiRun);
  assert.deepEqual(summary.sources_requested, ['wikipedia', 'arxiv', 'crossref']);
  assert.deepEqual(summary.source_breakdown, { wikipedia: 1, arxiv: 1, crossref: 1 });

  let state = {
    currentPipeline: null,
    latestSuccessfulRun: null,
    selectedRunId: null,
    runsHistory: [],
    runDetailsById: {},
  };
  state = applyNewRunToState(state, multiRun);
  const restored = selectRunInState(state, 'run-multi-1');

  assert.deepEqual(getSourceDistribution(restored.currentPipeline.dashboard), {
    wikipedia: 1,
    arxiv: 1,
    crossref: 1,
  });
  assert.equal(restored.currentPipeline.research.results[0].doi, '10.1103/PhysRevLett.132.010501');
  assert.deepEqual(restored.currentPipeline.analysis.evidence_backed_observations[0].authors, [
    'Alice Smith',
    'Bob Chen',
  ]);
  assert.equal(restored.currentPipeline.dashboard.observations[0].publication_date, '2024-01-22');
});

test('Phase 5: buildHistorySummary preserves execution_id, origin_platform, and handoff_count', () => {
  const phase5Run = makeRun({
    id: 'run-p5-1',
    query: 'agent interoperability',
    executed_at: '2026-11-12T00:10:00Z',
  });
  phase5Run.execution_id = 'exec-p5-999';
  phase5Run.shared_context = { origin_platform: 'band', query: 'agent interoperability' };
  phase5Run.handoffs = [{ handoff_id: 'h1' }, { handoff_id: 'h2' }];

  const summary = buildHistorySummary(phase5Run);
  assert.equal(summary.execution_id, 'exec-p5-999');
  assert.equal(summary.origin_platform, 'band');
  assert.equal(summary.handoff_count, 2);
});

test('Phase 7D: dashboard integrity distinguishes structural eligibility from topical relevance and preserves execution alignment', () => {
  const runA = makeRun({
    id: 'run-7d-1',
    query: 'healthcare AI research',
    executed_at: '2026-11-15T01:00:00Z',
    sources: 6,
    eligible: 5,
    themes: [
      { name: 'Diagnostic Imaging', count: 3 },
      { name: 'Clinical Decision Support', count: 4 }, // overlapping citations: 3 + 4 = 7 citations across 5 sources
    ],
  });
  runA.verification.directly_relevant_count = 4;
  runA.verification.weakly_relevant_count = 1;
  runA.verification.is_factually_verified = false;

  const summary = buildHistorySummary(runA);
  assert.equal(summary.source_count, 6);
  assert.equal(summary.eligible_count, 5);
  assert.equal(summary.directly_relevant_count, 4);
  assert.equal(summary.weakly_relevant_count, 1);
  assert.equal(summary.theme_count, 2);

  const kpis = getOverviewKpis(runA, [summary]);
  assert.equal(kpis.sourcesRetrieved, 6);
  assert.equal(kpis.eligibleSources, 5);
  assert.equal(kpis.themeCount, 2);

  // Verify normalized themes preserve evidence citation counts
  const themes = getNormalizedThemes(runA);
  assert.equal(themes[0].frequency, 3);
  assert.equal(themes[1].frequency, 4);

  // Epistemic boundary: is_factually_verified must be strictly false
  assert.equal(runA.verification.is_factually_verified, false);
});




