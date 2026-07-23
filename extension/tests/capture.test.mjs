import test from 'node:test';
import assert from 'node:assert/strict';
import { sanitizeNetworkEvent, createCaptureController } from '../capture.mjs';
import { createDebuggerLeaseManager } from '../lease.mjs';

test('sanitizes allowlisted Facebook metadata and drops secrets', () => {
  const value = sanitizeNetworkEvent({
    method: 'POST', url: 'https://www.facebook.com/api/post?token=secret',
    status: 200, resourceType: 'XHR', timingMs: 12,
  }, { captureId: 'cap-1', profileId: 'profile-1' });
  assert.deepEqual(value, {
    schemaVersion: 1, captureId: 'cap-1', method: 'POST', host: 'www.facebook.com',
    path: '/api/post', status: 200, resourceType: 'XHR', timingMs: 12,
    queryShape: ['key_hash:5a88237a'], valueAliases: { 'key_hash:5a88237a': 'v1' }
  });
});

test('rejects non-Facebook, login and response-body events', () => {
  for (const event of [
    { url: 'https://example.com/a' },
    { url: 'https://graph.facebook.com/v1/12345678901234567890' },
    { url: 'https://fbcdn.facebook.com/image/1' },
    { url: 'https://www.facebook.com/login/identify' },
    { url: 'https://www.facebook.com/a', responseBody: 'secret' }
  ]) assert.throws(() => sanitizeNetworkEvent(event, { captureId: 'c', profileId: 'p' }));
});

test('normalizes numeric and opaque path segments', () => {
  const value = sanitizeNetworkEvent({ url: 'https://www.facebook.com/api/12345678901234567890/very-long-opaque-token-value-that-must-not-persist' }, { captureId: 'c', profileId: 'p' });
  assert.equal(value.path, '/api/:segment/:segment');
});

test('normalizes encoded sensitive path segments', () => {
  const value = sanitizeNetworkEvent({ url: 'https://www.facebook.com/api/%74oken-value' }, { captureId: 'c', profileId: 'p' });
  assert.equal(value.path, '/api/:segment');
});

test('controller enforces event and byte caps and stop state', () => {
  const controller = createCaptureController({ captureId: 'c', profileId: 'p', maxEvents: 1 });
  controller.push({ method: 'GET', url: 'https://www.facebook.com/a' });
  assert.throws(() => controller.push({ method: 'GET', url: 'https://www.facebook.com/b' }), /event quota/);
  controller.stop('ttl');
  assert.equal(controller.status(), 'stopped');
  assert.throws(() => controller.push({ method: 'GET', url: 'https://www.facebook.com/c' }), /stopped/);
});

test('controller fails closed on TTL, UID drift, and debugger detach', () => {
  let clock = 1000;
  const controller = createCaptureController({ captureId: 'c', profileId: 'p', fbUid: 'uid-1', ttlMs: 1000, now: () => clock });
  assert.equal(controller.reconcile({ currentFbUid: 'uid-1', debuggerAttached: true }).status, 'running');
  assert.equal(controller.reconcile({ currentFbUid: 'uid-2' }).reason, 'uid_changed');
  const detached = createCaptureController({ captureId: 'c2', profileId: 'p', ttlMs: 1000, now: () => clock });
  assert.equal(detached.reconcile({ debuggerAttached: false }).reason, 'debugger_detached');
  const expired = createCaptureController({ captureId: 'c3', profileId: 'p', ttlMs: 1000, now: () => clock });
  clock = 2500;
  assert.equal(expired.reconcile().reason, 'ttl');
});

test('debugger lease is exclusive and owner-bound', () => {
  const leases = createDebuggerLeaseManager();
  leases.acquire(7, 'capture');
  assert.throws(() => leases.acquire(7, 'upload'), /busy/);
  assert.deepEqual(leases.reconcile(7, 'upload'), { active: false, reason: 'stale_or_missing' });
  assert.equal(leases.release(7, 'upload'), false);
  assert.equal(leases.release(7, 'capture'), true);
});
