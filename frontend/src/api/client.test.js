import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveApiBaseUrl, apiClient, API_BASE_URL } from './client.js';
import { checkBackendHealth } from './research.js';

test('api client base URL defaults to port 8010 in local environment', () => {
  assert.equal(apiClient.defaults.baseURL, 'http://127.0.0.1:8010');
  assert.equal(apiClient.defaults.headers['Content-Type'], 'application/json');
  assert.equal(typeof apiClient.get, 'function');
  assert.equal(typeof apiClient.post, 'function');
});

test('resolveApiBaseUrl strips trailing slashes', () => {
  assert.equal(
    resolveApiBaseUrl({ override: 'https://intelliscope-backend.onrender.com/' }),
    'https://intelliscope-backend.onrender.com'
  );
  assert.equal(
    resolveApiBaseUrl({ override: 'https://intelliscope-backend.onrender.com///' }),
    'https://intelliscope-backend.onrender.com'
  );
});

test('resolveApiBaseUrl automatically resolves Render backend from frontend window.location', () => {
  const mockRenderWindow = {
    location: {
      hostname: 'intelliscope-frontend.onrender.com',
      protocol: 'https:',
    },
  };
  const resolved = resolveApiBaseUrl({ window: mockRenderWindow });
  assert.equal(resolved, 'https://intelliscope-backend.onrender.com');
});

test('resolveApiBaseUrl preserves custom Render branch preview hostnames', () => {
  const mockBranchWindow = {
    location: {
      hostname: 'my-preview-frontend.onrender.com',
      protocol: 'https:',
    },
  };
  const resolved = resolveApiBaseUrl({ window: mockBranchWindow });
  assert.equal(resolved, 'https://my-preview-backend.onrender.com');
});

test('resolveApiBaseUrl falls back to local port 8010 for localhost window', () => {
  const mockLocalWindow = {
    location: {
      hostname: 'localhost',
      protocol: 'http:',
    },
  };
  const resolved = resolveApiBaseUrl({ window: mockLocalWindow });
  assert.equal(resolved, 'http://127.0.0.1:8010');
});

test('checkBackendHealth is exported and targets /health', () => {
  assert.equal(typeof checkBackendHealth, 'function');
});
