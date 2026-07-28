const APPROVED = (host) => (host === 'facebook.com' || host.endsWith('.facebook.com')) && !host.includes('graph.facebook.com') && !host.endsWith('.fbcdn.net') && host !== 'fbcdn.net';
const FORBIDDEN_PATHS = new Set(['/login', '/login/identify', '/checkpoint']);
const SENSITIVE = ['token', 'cookie', 'auth', 'pass', 'secret', 'session', 'jwt', 'fb_dtsg', 'lsd', 'c_user'];

function safeKey(key) {
  const lower = key.toLowerCase();
  const digest = [...key].reduce((hash, char) => ((hash ^ char.charCodeAt(0)) * 16777619) >>> 0, 2166136261).toString(16).padStart(8, '0');
  return SENSITIVE.some((part) => lower.includes(part))
    ? `key_hash:${digest}`
    : key.slice(0, 64);
}

export function sanitizeNetworkEvent(input, scope) {
  if (!input || typeof input !== 'object' || !scope?.captureId || !scope?.profileId) throw new Error('invalid capture scope');
  if (Object.hasOwn(input, 'responseBody') || Object.hasOwn(input, 'requestHeaders') || Object.hasOwn(input, 'postData')) throw new Error('secret-bearing fields rejected');
  const parsed = new URL(String(input.url || ''));
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password || parsed.hash) throw new Error('unsafe URL');
  const host = parsed.hostname.toLowerCase().replace(/\.$/, '');
  if (!APPROVED(host) || host.includes('fbcdn')) throw new Error('host not approved');
  const decodedPath = decodeURIComponent(parsed.pathname || '/');
  const path = decodedPath.split('/').map((part) => {
    if (!part) return '';
    if (/^\d+$/.test(part) || part.length > 48 || /token|auth|secret|cookie|session|dtsg|lsd/i.test(part)) return ':segment';
    return part;
  }).join('/');
  if (FORBIDDEN_PATHS.has(path) || path.startsWith('/login/') || path.startsWith('/checkpoint')) throw new Error('auth path excluded');
  const queryShape = [...new Set([...parsed.searchParams.keys()].sort())].map(safeKey);
  const valueAliases = Object.fromEntries(queryShape.map((key) => [key, 'v1']));
  const method = String(input.method || 'GET').toUpperCase();
  if (!['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'].includes(method)) throw new Error('method not allowed');
  const status = input.status == null ? null : Number(input.status);
  const timingMs = input.timingMs == null ? null : Number(input.timingMs);
  if (status != null && (!Number.isInteger(status) || status < 100 || status > 599)) throw new Error('status invalid');
  if (timingMs != null && (!Number.isFinite(timingMs) || timingMs < 0 || timingMs > 600000)) throw new Error('timing invalid');
  return { schemaVersion: 1, captureId: String(scope.captureId).slice(0, 128), method, host, path: path.slice(0, 2048), status, resourceType: String(input.resourceType || 'Other').slice(0, 64), timingMs, queryShape, valueAliases };
}

export function createCaptureController({ captureId, profileId, fbUid = null, maxEvents = 1000, maxBytes = 1024 * 1024, ttlMs = 15 * 60 * 1000, now = () => Date.now() }) {
  if (!Number.isInteger(maxEvents) || maxEvents < 1 || !Number.isInteger(maxBytes) || maxBytes < 1) throw new Error('capture quotas must be positive integers');
  let stopped = false;
  let reason = null;
  const expiresAt = now() + Math.min(Math.max(ttlMs, 1000), 24 * 60 * 60 * 1000);
  let events = 0;
  let bytes = 0;
  return {
    push(input) {
      if (stopped) throw new Error('capture is stopped');
      if (now() >= expiresAt) { stopped = true; reason = 'ttl'; throw new Error('capture TTL expired'); }
      if (events >= maxEvents) throw new Error('event quota exceeded');
      const event = sanitizeNetworkEvent(input, { captureId, profileId });
      const size = JSON.stringify(event).length;
      if (bytes + size > maxBytes) throw new Error('byte quota exceeded');
      events += 1; bytes += size;
      return event;
    },
    stop(value = 'manual') { stopped = true; reason = value; },
    reconcile({ currentFbUid = fbUid, debuggerAttached = true } = {}) {
      if (!debuggerAttached) { stopped = true; reason = 'debugger_detached'; }
      else if (fbUid !== null && currentFbUid !== fbUid) { stopped = true; reason = 'uid_changed'; }
      else if (now() >= expiresAt) { stopped = true; reason = 'ttl'; }
      return { status: stopped ? 'stopped' : 'running', reason };
    },
    status() { return stopped ? 'stopped' : 'running'; },
    stopReason() { return reason; },
  };
}
