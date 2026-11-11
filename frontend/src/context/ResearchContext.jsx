import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  runPipeline,
  getAgentsStatus,
  checkBackendHealth,
  getPipelineHistory,
  getPipelineRunById,
} from '../api/research';
import {
  applyNewRunToState,
  applyBackendHistorySync,
  selectRunInState,
  selectLatestRunInState,
  mergePipelineHistory,
} from './pipelineState';

const ResearchContext = createContext(null);

const STORAGE_KEY_CURRENT = 'intelliscope_current_pipeline';
const STORAGE_KEY_HISTORY = 'intelliscope_pipeline_history';
const STORAGE_KEY_DETAILS = 'intelliscope_pipeline_details';

function loadJsonStorage(storage, key, fallback) {
  try {
    const saved = storage.getItem(key);
    return saved ? JSON.parse(saved) : fallback;
  } catch {
    return fallback;
  }
}

export function ResearchProvider({ children }) {
  const [pipelineState, setPipelineState] = useState(() => {
    const savedCurrent = loadJsonStorage(sessionStorage, STORAGE_KEY_CURRENT, null);
    const savedHistory = loadJsonStorage(localStorage, STORAGE_KEY_HISTORY, []);
    const savedDetails = loadJsonStorage(localStorage, STORAGE_KEY_DETAILS, {});

    if (savedCurrent?.pipeline_id && !savedDetails[savedCurrent.pipeline_id]) {
      savedDetails[savedCurrent.pipeline_id] = savedCurrent;
    }

    return {
      currentPipeline: savedCurrent,
      latestSuccessfulRun: savedCurrent?.status === 'success' ? savedCurrent : null,
      selectedRunId: null,
      runsHistory: Array.isArray(savedHistory) ? savedHistory : [],
      runDetailsById: savedDetails && typeof savedDetails === 'object' ? savedDetails : {},
    };
  });

  // Fleet agent statuses from GET /agents/status
  const [agentsFleet, setAgentsFleet] = useState(null);
  const [fleetLoading, setFleetLoading] = useState(true);

  // Connection & execution states
  const [backendHealth, setBackendHealth] = useState({ healthy: false, checking: true });
  const [isExecuting, setIsExecuting] = useState(false);
  const [isSelectingRun, setIsSelectingRun] = useState(false);
  const [executionError, setExecutionError] = useState(null);

  // Sync current pipeline to session storage
  useEffect(() => {
    try {
      if (pipelineState.currentPipeline) {
        sessionStorage.setItem(STORAGE_KEY_CURRENT, JSON.stringify(pipelineState.currentPipeline));
      } else {
        sessionStorage.removeItem(STORAGE_KEY_CURRENT);
      }
    } catch {
      // ignore storage quota errors
    }
  }, [pipelineState.currentPipeline]);

  // Sync history & bounded full run details cache to local storage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(pipelineState.runsHistory));
      // Persist details only for retained history IDs (max 15) to respect storage limits
      const retainedIds = new Set(
        (pipelineState.runsHistory || []).slice(0, 15).map((r) => r.id || r.pipeline_id)
      );
      if (pipelineState.latestSuccessfulRun?.pipeline_id) {
        retainedIds.add(pipelineState.latestSuccessfulRun.pipeline_id);
      }
      if (pipelineState.currentPipeline?.pipeline_id) {
        retainedIds.add(pipelineState.currentPipeline.pipeline_id);
      }
      const compactDetails = {};
      for (const id of retainedIds) {
        if (pipelineState.runDetailsById[id]) {
          compactDetails[id] = pipelineState.runDetailsById[id];
        }
      }
      localStorage.setItem(STORAGE_KEY_DETAILS, JSON.stringify(compactDetails));
    } catch {
      // ignore quota errors
    }
  }, [pipelineState.runsHistory, pipelineState.runDetailsById, pipelineState.latestSuccessfulRun, pipelineState.currentPipeline]);

  // Synchronize latest BAND / backend pipeline runs and health status
  const checkStatus = useCallback(async () => {
    try {
      const health = await checkBackendHealth();
      const healthy = health?.status === 'healthy';
      setBackendHealth({ healthy, checking: false });

      if (healthy) {
        const [statusData, historyData] = await Promise.allSettled([
          getAgentsStatus(),
          getPipelineHistory(20),
        ]);

        if (statusData.status === 'fulfilled' && statusData.value?.agents) {
          setAgentsFleet(statusData.value.agents);
        }

        if (historyData.status === 'fulfilled' && historyData.value) {
          setPipelineState((prev) => applyBackendHistorySync(prev, historyData.value));
        }
      }
    } catch (err) {
      setBackendHealth({ healthy: false, checking: false, error: err.message });
    } finally {
      setFleetLoading(false);
    }
  }, []);

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 10000); // 10s poll to catch live BAND runs quickly
    const handleFocus = () => checkStatus();
    window.addEventListener('focus', handleFocus);
    return () => {
      clearInterval(interval);
      window.removeEventListener('focus', handleFocus);
    };
  }, [checkStatus]);

  // Execute research via POST /pipeline
  const startResearch = async (query, limit = 5) => {
    setIsExecuting(true);
    setExecutionError(null);

    try {
      const response = await runPipeline({ query, limit });
      setPipelineState((prev) => applyNewRunToState(prev, response));

      if (response.status === 'failed') {
        const failErr = new Error(response.summary || 'Pipeline execution failed.');
        failErr.status = 'failed';
        failErr.response_recorded = true;
        setExecutionError(failErr);
        throw failErr;
      }

      // Trigger background sync so backend and frontend history IDs are aligned
      checkStatus().catch(() => {});
      return response;
    } catch (err) {
      // If network/API error occurred without response, still record failed attempt in history
      // without overwriting last successful research!
      if (!err?.response_recorded && err?.status !== 'failed') {
        const failedSummary = {
          id: `failed-${Date.now()}`,
          pipeline_id: `failed-${Date.now()}`,
          query: query.trim(),
          status: 'failed',
          duration_ms: 0,
          executed_at: new Date().toISOString(),
          source_count: 0,
          eligible_count: 0,
          quality_score: 0,
          theme_count: 0,
          summary: err?.message || 'Pipeline request failed.',
        };
        setPipelineState((prev) => ({
          ...prev,
          runsHistory: mergePipelineHistory(prev.runsHistory, [failedSummary]),
        }));
      }
      setExecutionError(err);
      throw err;
    } finally {
      setIsExecuting(false);
    }
  };

  // Select a historical run and display its own sources, verification, insights, and dashboard
  const selectRun = useCallback(
    async (pipelineId) => {
      if (!pipelineId) return null;

      const cached = pipelineState.runDetailsById?.[pipelineId];
      if (cached) {
        setPipelineState((prev) => selectRunInState(prev, pipelineId, cached));
        return cached;
      }

      setIsSelectingRun(true);
      try {
        const fetched = await getPipelineRunById(pipelineId);
        if (fetched) {
          setPipelineState((prev) => selectRunInState(prev, pipelineId, fetched));
        }
        return fetched;
      } catch (err) {
        return null;
      } finally {
        setIsSelectingRun(false);
      }
    },
    [pipelineState.runDetailsById]
  );

  const selectLatestRun = useCallback(() => {
    setPipelineState((prev) => selectLatestRunInState(prev));
  }, []);

  const clearCurrentResearch = () => {
    setPipelineState((prev) => ({
      ...prev,
      currentPipeline: null,
      selectedRunId: null,
    }));
    setExecutionError(null);
  };

  const clearHistory = () => {
    setPipelineState((prev) => ({
      ...prev,
      runsHistory: [],
      runDetailsById: prev.currentPipeline?.pipeline_id
        ? { [prev.currentPipeline.pipeline_id]: prev.currentPipeline }
        : {},
    }));
    localStorage.removeItem(STORAGE_KEY_HISTORY);
    localStorage.removeItem(STORAGE_KEY_DETAILS);
  };

  const {
    currentPipeline,
    latestSuccessfulRun,
    selectedRunId,
    runsHistory,
    runDetailsById,
  } = pipelineState;

  const isViewingHistoricalRun = Boolean(
    selectedRunId &&
      latestSuccessfulRun &&
      selectedRunId !== latestSuccessfulRun.pipeline_id
  );

  const value = {
    currentPipeline,
    latestSuccessfulRun,
    selectedRunId,
    isViewingHistoricalRun,
    runsHistory,
    runDetailsById,
    agentsFleet,
    fleetLoading,
    backendHealth,
    isExecuting,
    isSelectingRun,
    executionError,
    startResearch,
    selectRun,
    selectLatestRun,
    clearCurrentResearch,
    clearHistory,
    refreshStatus: checkStatus,
  };

  return <ResearchContext.Provider value={value}>{children}</ResearchContext.Provider>;
}

export function useResearch() {
  const context = useContext(ResearchContext);
  if (!context) {
    throw new Error('useResearch must be used within a ResearchProvider');
  }
  return context;
}
