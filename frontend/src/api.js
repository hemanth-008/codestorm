/**
 * Typed API client for the FleetTwin backend.
 *
 * Every function mirrors a route from CONTRACT.md § 7. When VITE_USE_MOCK=1
 * the SSE hook falls back to the built-in mock stream (see mock.js).
 *
 * @module api
 */

const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

/** @type {string|null} JWT access token set after login */
let _token = null;

/** Store JWT token for authenticated requests */
export function setToken(token) {
  _token = token;
}

/** Get stored JWT token */
export function getToken() {
  return _token;
}

/** Clear stored JWT token */
export function clearToken() {
  _token = null;
}

/**
 * Build headers including auth if a token is stored.
 * @param {Object} [extra] - additional headers
 * @returns {HeadersInit}
 */
function headers(extra = {}) {
  const h = { 'Content-Type': 'application/json', ...extra };
  if (_token) h['Authorization'] = `Bearer ${_token}`;
  return h;
}

/**
 * Typed fetch helper.
 * @param {string} path
 * @param {RequestInit} [opts]
 * @returns {Promise<any>}
 */
async function api(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: headers(opts.headers),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text}`);
  }
  if (res.status === 204 || res.status === 202) return null;
  return res.json();
}

// ─── Fleet & Robots ─────────────────────────────────────────

/** @returns {Promise<import('./types').RobotFrame[]>} */
export function getFleet() {
  return api('/api/fleet');
}

/**
 * @param {string} id
 * @returns {Promise<{frame: import('./types').RobotFrame, history: import('./types').TwinState[], events: import('./types').Event[]}>}
 */
export function getRobot(id) {
  return api(`/api/robots/${id}`);
}

/** @returns {Promise<import('./types').Event[]>} */
export function getEvents(limit = 50) {
  return api(`/api/events?limit=${limit}`);
}

// ─── Decision & Override ────────────────────────────────────

/**
 * @param {string} [robotId]
 * @returns {Promise<import('./types').Decision>}
 */
export function getDecision(robotId) {
  const q = robotId ? `?robot_id=${robotId}` : '';
  return api(`/api/decision${q}`);
}

/**
 * @param {{robot_id?: string, action: import('./types').Action, seconds?: number}} body
 * @returns {Promise<import('./types').OverrideState>}
 */
export function postOverride(body) {
  return api('/api/override', {
    method: 'POST',
    body: JSON.stringify({ seconds: 15, ...body }),
  });
}

// ─── Telemetry ──────────────────────────────────────────────

/**
 * @param {import('./types').Telemetry} tel
 * @returns {Promise<null>}
 */
export function postTelemetry(tel) {
  return api('/api/telemetry', {
    method: 'POST',
    body: JSON.stringify(tel),
  });
}

// ─── Attacks ────────────────────────────────────────────────

/**
 * @param {import('./types').AttackSpec} spec
 * @returns {Promise<any>}
 */
export function injectAttack(spec) {
  return api('/api/attacks/inject', {
    method: 'POST',
    body: JSON.stringify(spec),
  });
}

/**
 * @param {{robot_id?: string}} body
 * @returns {Promise<any>}
 */
export function clearAttacks(body = {}) {
  return api('/api/attacks/clear', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ─── Simulation ─────────────────────────────────────────────

/**
 * Reset the backend simulation.
 * @returns {Promise<any>}
 */
export function resetSim() {
  return api('/api/sim/reset', { method: 'POST' });
}

// ─── Missions ───────────────────────────────────────────────

/** @returns {Promise<Object<string, import('./types').Mission>>} */
export function getMissions() {
  return api('/api/missions');
}

/**
 * @param {import('./types').Mission} mission
 * @returns {Promise<import('./types').SimResult>}
 */
export function simulateMission(mission) {
  return api('/api/missions/simulate', {
    method: 'POST',
    body: JSON.stringify(mission),
  });
}

/**
 * @param {import('./types').Mission} mission
 * @param {boolean} [force]
 * @returns {Promise<any>}
 */
export function deployMission(mission, force = false) {
  const q = force ? '?force=1' : '';
  return api(`/api/missions/deploy${q}`, {
    method: 'POST',
    body: JSON.stringify(mission),
  });
}

// ─── Eval ───────────────────────────────────────────────────

/**
 * @param {number} [seed]
 * @returns {Promise<import('./types').EvalResult>}
 */
export function runEval(seed = 42) {
  return api(`/api/eval/run?seed=${seed}`, { method: 'POST' });
}

/** @returns {Promise<import('./types').EvalResult>} */
export function getEvalLatest() {
  return api('/api/eval/latest');
}

// ─── Auth ───────────────────────────────────────────────────

/**
 * @param {string} username
 * @param {string} password
 * @returns {Promise<import('./types').Token>}
 */
export function login(username, password) {
  return api('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

// ─── Health & Monitoring ────────────────────────────────────

/** @returns {Promise<any>} */
export function getHealth() {
  return api('/health');
}

/**
 * Open an SSE connection to the stream endpoint.
 * @returns {EventSource}
 */
export function openStream() {
  const url = `${BASE}/api/stream`;
  return new EventSource(url);
}
