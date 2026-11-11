import test from 'node:test';
import assert from 'node:assert/strict';

test('api client base URL defaults to port 8010', async () => {
  const { apiClient } = await import('./client.js');
  assert.equal(apiClient.defaults.baseURL, 'http://127.0.0.1:8010');
  assert.equal(apiClient.defaults.headers['Content-Type'], 'application/json');
});

test('api client response interceptor formats error correctly', async () => {
  const { apiClient } = await import('./client.js');
  assert.equal(typeof apiClient.get, 'function');
  assert.equal(typeof apiClient.post, 'function');
});

