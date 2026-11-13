import apiClient from './client';

/**
 * Execute the unified end-to-end multi-agent research pipeline.
 * Calls POST /pipeline with {"query": topic, "limit": limit, "sources": sources}
 */
export async function runPipeline({ query, limit = 5, sources = ['wikipedia'], originPlatform = 'web_ui' }) {
  return apiClient.post('/pipeline', {
    query: query.trim(),
    limit: Number(limit),
    sources: Array.isArray(sources) && sources.length > 0 ? sources : ['wikipedia'],
    origin_platform: originPlatform,
  });
}

/**
 * Retrieve retained pipeline run history and latest successful run from backend.
 * Calls GET /pipeline/history
 */
export async function getPipelineHistory(limit = 20) {
  return apiClient.get('/pipeline/history', { params: { limit } });
}

/**
 * Retrieve the latest successful pipeline run (never overwritten by failed runs).
 * Calls GET /pipeline/latest
 */
export async function getLatestPipelineRun() {
  return apiClient.get('/pipeline/latest');
}

/**
 * Retrieve full structured output of a historical pipeline run by ID.
 * Calls GET /pipeline/{pipelineId}
 */
export async function getPipelineRunById(pipelineId) {
  return apiClient.get(`/pipeline/${encodeURIComponent(pipelineId)}`);
}

/**
 * Retrieve operational status and capabilities of all platform agents.
 * Calls GET /agents/status
 */
export async function getAgentsStatus() {
  return apiClient.get('/agents/status');
}

/**
 * Check backend health status.
 * Calls GET /health
 */
export async function checkBackendHealth() {
  return apiClient.get('/health');
}

/**
 * Direct call to Data Collector Agent.
 * Calls POST /research
 */
export async function collectResearch({ query, limit = 5, sources = ['wikipedia'] }) {
  return apiClient.post('/research', {
    query: query.trim(),
    limit: Number(limit),
    sources: Array.isArray(sources) && sources.length > 0 ? sources : ['wikipedia'],
  });
}

/**
 * Direct call to Research Verification Agent.
 * Calls POST /verify
 */
export async function verifyResearch(payload) {
  return apiClient.post('/verify', payload);
}

/**
 * Direct call to Insight Analyst Agent.
 * Calls POST /analyze
 */
export async function analyzeResearch(payload) {
  return apiClient.post('/analyze', payload);
}

/**
 * Direct call to Dashboard Builder Agent.
 * Calls POST /dashboard
 */
export async function buildDashboardSpec(payload) {
  return apiClient.post('/dashboard', payload);
}

/**
 * Retrieve honest readiness & credential status for sponsor integrations.
 * Calls GET /integrations/status
 */
export async function getIntegrationsStatus() {
  return apiClient.get('/integrations/status');
}

/**
 * Trigger a safe non-mutating check probe for one sponsor platform.
 * Calls POST /integrations/check/{platformId}
 */
export async function checkIntegrationPlatform(platformId) {
  return apiClient.post(`/integrations/check/${encodeURIComponent(platformId)}`);
}

/**
 * Dispatch a structured task delegation request to a sponsor adapter.
 * Calls POST /integrations/delegate
 */
export async function delegateIntegrationTask(payload) {
  return apiClient.post('/integrations/delegate', payload);
}

