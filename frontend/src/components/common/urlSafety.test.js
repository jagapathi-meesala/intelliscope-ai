import test from 'node:test';
import assert from 'node:assert/strict';

function isSecureHttpsUrl(href) {
  if (!href) return false;
  try {
    const url = new URL(href);
    return url.protocol === 'https:';
  } catch {
    return false;
  }
}

test('isSecureHttpsUrl correctly detects valid HTTPS Wikipedia URLs', () => {
  assert.equal(isSecureHttpsUrl('https://en.wikipedia.org/wiki/Quantum_computing'), true);
  assert.equal(isSecureHttpsUrl('https://en.wikipedia.org/wiki/Artificial_intelligence'), true);
});

test('isSecureHttpsUrl rejects insecure HTTP or malformed URLs', () => {
  assert.equal(isSecureHttpsUrl('http://en.wikipedia.org/wiki/Insecure'), false);
  assert.equal(isSecureHttpsUrl('javascript:alert(1)'), false);
  assert.equal(isSecureHttpsUrl(''), false);
  assert.equal(isSecureHttpsUrl(null), false);
});

