/**
 * Pure state-transition and normalization helpers for IntelliScope AI pipeline state.
 * Extracted for deterministic behavior across BAND/frontend synchronization and unit tests.
 */

export function normalizeThemeItem(item) {
  if (!item || typeof item !== 'object') return null;
  const name = String(item.theme || item.name || '').trim();
  if (!name) return null;

  const sources = Array.isArray(item.sources)
    ? item.sources.filter((s) => typeof s === 'string' && s.trim().startsWith('https://'))
    : [];

  const rawCount =
    item.frequency !== undefined && item.frequency !== null
      ? item.frequency
      : item.evidence_count;

  const parsedCount =
    rawCount !== undefined && rawCount !== null && !Number.isNaN(Number(rawCount))
      ? Math.max(0, Number(rawCount))
      : sources.length;

  return {
    theme: name,
    name,
    description: String(item.description || '').trim(),
    frequency: parsedCount,
    evidence_count: parsedCount,
    sources,
  };
}

/**
 * Extract normalized themes consistently from a PipelineResponse, Dashboard, or Analysis object.
 * Never fabricates themes when empty.
 */
export function getNormalizedThemes(source) {
  if (!source || typeof source !== 'object') return [];

  let candidates = [];
  if (Array.isArray(source.themes) && source.themes.length > 0) {
    candidates = source.themes;
  } else if (Array.isArray(source.key_themes) && source.key_themes.length > 0) {
    candidates = source.key_themes;
  } else if (source.dashboard) {
    candidates =
      (Array.isArray(source.dashboard.themes) && source.dashboard.themes.length > 0
        ? source.dashboard.themes
        : source.dashboard.key_themes) || [];
  } else if (source.analysis && Array.isArray(source.analysis.key_themes)) {
    candidates = source.analysis.key_themes;
  }

  if ((!candidates || candidates.length === 0) && source.analysis && Array.isArray(source.analysis.key_themes)) {
    candidates = source.analysis.key_themes;
  }

  return (candidates || []).map(normalizeThemeItem).filter(Boolean);
}

/**
 * Build a uniform history summary record from a full PipelineResponse.
 */
export function buildHistorySummary(response) {
  if (!response) return null;
  const themes = getNormalizedThemes(response);

  return {
    id: response.pipeline_id,
    pipeline_id: response.pipeline_id,
    execution_id: response.execution_id || response.pipeline_id,
    origin_platform: response.shared_context?.origin_platform || 'api',
    handoff_count: Array.isArray(response.handoffs) ? response.handoffs.length : 0,
    query: response.query,
    status: response.status,
    duration_ms: response.total_duration_ms ?? 0,
    total_duration_ms: response.total_duration_ms ?? 0,
    executed_at: response.executed_at || new Date().toISOString(),
    source_count: response.research?.result_count ?? 0,
    eligible_count: response.analysis?.eligible_sources_count ?? 0,
    directly_relevant_count: response.verification?.directly_relevant_count ?? 0,
    weakly_relevant_count: response.verification?.weakly_relevant_count ?? 0,
    excluded_count:
      response.analysis?.excluded_sources_count ??
      response.verification?.excluded_count ??
      0,
    quality_score: response.verification?.quality_score ?? 0,
    theme_count: themes.length,
    sources_requested: response.research?.sources_requested || ['wikipedia'],
    source_breakdown: response.research?.source_breakdown || {},
    summary: response.summary || response.analysis?.executive_summary || null,
  };
}

/**
 * Extract normalized provider counts cleanly without fabrication.
 */
export function getSourceDistribution(source) {
  if (!source || typeof source !== 'object') return {};
  if (source.source_distribution && typeof source.source_distribution === 'object') {
    return source.source_distribution;
  }
  if (source.dashboard?.source_distribution && typeof source.dashboard.source_distribution === 'object') {
    return source.dashboard.source_distribution;
  }
  if (source.analysis?.source_distribution && typeof source.analysis.source_distribution === 'object') {
    return source.analysis.source_distribution;
  }
  if (source.research?.source_breakdown && typeof source.research.source_breakdown === 'object') {
    return source.research.source_breakdown;
  }
  return {};
}

function normalizeBackendSummary(item) {
  if (!item) return null;
  const id = item.pipeline_id || item.id;
  if (!id) return null;
  return {
    ...item,
    id,
    pipeline_id: id,
    duration_ms: item.duration_ms ?? item.total_duration_ms ?? 0,
    total_duration_ms: item.total_duration_ms ?? item.duration_ms ?? 0,
  };
}

/**
 * Merge backend and local history summaries without duplicates, ordered newest-first.
 */
export function mergePipelineHistory(existingHistory = [], backendSummaries = [], maxItems = 20) {
  const byId = new Map();

  for (const raw of existingHistory) {
    const norm = normalizeBackendSummary(raw);
    if (norm) byId.set(norm.id, norm);
  }

  for (const raw of backendSummaries) {
    const norm = normalizeBackendSummary(raw);
    if (norm) {
      byId.set(norm.id, { ...(byId.get(norm.id) || {}), ...norm });
    }
  }

  const merged = Array.from(byId.values());
  merged.sort((a, b) => {
    const tA = a.executed_at ? Date.parse(a.executed_at) : 0;
    const tB = b.executed_at ? Date.parse(b.executed_at) : 0;
    return (Number.isNaN(tB) ? 0 : tB) - (Number.isNaN(tA) ? 0 : tA);
  });

  return merged.slice(0, maxItems);
}

export function isSuccessfulPipeline(run) {
  return Boolean(run && run.status === 'success' && (run.dashboard || run.analysis));
}

/**
 * Apply a newly executed run to state.
 * Failed runs are recorded in history but NEVER overwrite currentPipeline / latestSuccessfulRun.
 */
export function applyNewRunToState(prevState, response) {
  if (!response) return prevState;

  const summary = buildHistorySummary(response);
  const nextHistory = mergePipelineHistory(prevState.runsHistory || [], summary ? [summary] : []);
  const nextDetails = { ...(prevState.runDetailsById || {}) };
  if (response.pipeline_id) {
    nextDetails[response.pipeline_id] = response;
  }

  if (isSuccessfulPipeline(response)) {
    return {
      ...prevState,
      currentPipeline: response,
      latestSuccessfulRun: response,
      selectedRunId: null,
      runsHistory: nextHistory,
      runDetailsById: nextDetails,
    };
  }

  // Failed or non-success run: preserve last successful result as currentPipeline
  return {
    ...prevState,
    runsHistory: nextHistory,
    runDetailsById: nextDetails,
  };
}

/**
 * Apply backend GET /pipeline/history payload into frontend state.
 * Automatically updates active view to the backend's latest successful run
 * unless the user has explicitly selected an older run from history.
 */
export function applyBackendHistorySync(prevState, historyPayload) {
  if (!historyPayload || typeof historyPayload !== 'object') return prevState;

  const backendRuns = Array.isArray(historyPayload.runs) ? historyPayload.runs : [];
  const nextHistory = mergePipelineHistory(prevState.runsHistory || [], backendRuns);

  const nextDetails = { ...(prevState.runDetailsById || {}) };
  const backendLatest = historyPayload.latest_successful_run || null;
  if (backendLatest && backendLatest.pipeline_id) {
    nextDetails[backendLatest.pipeline_id] = backendLatest;
  }

  const resolvedLatest = backendLatest || prevState.latestSuccessfulRun || null;

  // Determine which run should be active in UI
  let nextCurrent = prevState.currentPipeline || null;
  const userPinnedHistorical = Boolean(prevState.selectedRunId);

  if (!userPinnedHistorical && resolvedLatest) {
    // Follow the latest successful run (e.g., newer BAND run replaces stale older topic)
    nextCurrent = resolvedLatest;
  } else if (prevState.selectedRunId && nextDetails[prevState.selectedRunId]) {
    nextCurrent = nextDetails[prevState.selectedRunId];
  } else if (!nextCurrent && resolvedLatest) {
    nextCurrent = resolvedLatest;
  }

  return {
    ...prevState,
    currentPipeline: nextCurrent,
    latestSuccessfulRun: resolvedLatest,
    runsHistory: nextHistory,
    runDetailsById: nextDetails,
  };
}

/**
 * Select a specific historical run to inspect its sources, verification, insights, and dashboard.
 */
export function selectRunInState(prevState, pipelineId, resolvedRun = null) {
  const candidate = resolvedRun || prevState.runDetailsById?.[pipelineId];
  if (!candidate) return prevState;

  // Never allow a failed run with no outputs to wipe the dashboard unless restoring a valid snapshot
  if (candidate.status === 'failed' && !candidate.dashboard && !candidate.analysis) {
    return prevState;
  }

  const nextDetails = { ...(prevState.runDetailsById || {}), [pipelineId]: candidate };
  const isLatest = prevState.latestSuccessfulRun?.pipeline_id === pipelineId;

  return {
    ...prevState,
    currentPipeline: candidate,
    selectedRunId: isLatest ? null : pipelineId,
    runDetailsById: nextDetails,
  };
}

/**
 * Return UI to the latest successful pipeline run.
 */
export function selectLatestRunInState(prevState) {
  if (!prevState.latestSuccessfulRun) {
    return { ...prevState, selectedRunId: null };
  }
  return {
    ...prevState,
    currentPipeline: prevState.latestSuccessfulRun,
    selectedRunId: null,
  };
}

/**
 * Compute Overview KPI values strictly matching the selected/latest run without double counting.
 */
export function getOverviewKpis(currentPipeline, runsHistory = []) {
  const uniqueIds = new Set((runsHistory || []).map((r) => r.id || r.pipeline_id).filter(Boolean));
  if (currentPipeline?.pipeline_id) {
    uniqueIds.add(currentPipeline.pipeline_id);
  }

  const themes = getNormalizedThemes(currentPipeline);

  return {
    totalRuns: uniqueIds.size,
    sourcesRetrieved: currentPipeline?.research?.result_count ?? 0,
    eligibleSources: currentPipeline?.analysis?.eligible_sources_count ?? 0,
    themeCount: themes.length,
  };
}

