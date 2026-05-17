import { attachAgentToken, supabase } from './supabaseClient'
import { API_URL } from './config'

/**
 * Auth tokens live in sessionStorage (NOT localStorage) so a JWT cannot
 * outlive the browser tab it was issued in. Closing the tab or browser
 * window forces a fresh login on the next visit, which:
 *   - matches the requirement spec (session-scoped storage), and
 *   - shrinks the blast radius of XSS exfiltration (a malicious script
 *     loaded in a different tab cannot read this tab's token).
 */
const TOKEN_KEY = 'resqnet_auth_token'
const LEGACY_TOKEN_KEY = 'resqnet_token'
const USER_KEY = 'resqnet_user'

export function getAuthToken() {
  return (
    sessionStorage.getItem(TOKEN_KEY) ||
    sessionStorage.getItem(LEGACY_TOKEN_KEY)
  )
}

/**
 * Persist a freshly-issued Supabase session locally and propagate the JWT
 * to the shared Supabase client so Realtime + PostgREST also authenticate
 * as this agent for the remainder of the tab's lifetime.
 *
 * The backend's `_session_payload()` already exposes the agent UUID both
 * inside `session.user.agent_id` AND at the top level as `session.agent_id`.
 * We store `session.user` so downstream code can read `user.agent_id`
 * without ever having to decode the JWT in the browser.
 */
export function setAuthSession(session) {
  sessionStorage.setItem(TOKEN_KEY, session.access_token)
  sessionStorage.removeItem(LEGACY_TOKEN_KEY)
  sessionStorage.setItem(USER_KEY, JSON.stringify(session.user))
  attachAgentToken(session.access_token)
}

export function clearAuthSession() {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(LEGACY_TOKEN_KEY)
  sessionStorage.removeItem(USER_KEY)
  attachAgentToken(null)
}

export function getStoredUser() {
  try {
    return JSON.parse(sessionStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

/** Convenience accessor: the JWT-resolved agent UUID, or `null` if signed out. */
export function getCurrentAgentId() {
  return getStoredUser()?.agent_id ?? getStoredUser()?.id ?? null
}

/**
 * Error thrown by `apiFetch` on non-2xx responses. We attach the HTTP
 * `status` and the parsed `detail` payload so call sites can branch on
 * structured failures (e.g. claim collisions return 409 with
 * `{ reason: 'ALREADY_CLAIMED', message }`) without having to string-match.
 */
export class ApiError extends Error {
  constructor(message, { status, detail } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  const token = getAuthToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_URL}${path}`, { ...options, headers })
  const data = await res.json().catch(() => ({}))

  if (!res.ok) {
    const detail = data.detail ?? data.message
    const msg =
      (detail && typeof detail === 'object' && detail.message) ||
      (typeof detail === 'string' ? detail : null) ||
      `Request failed (${res.status})`
    throw new ApiError(msg, { status: res.status, detail })
  }
  return data
}

export async function agentLogin(email, password) {
  const session = await apiFetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  setAuthSession(session)
  return session
}

export async function agentSignup(email, password, name) {
  const session = await apiFetch('/api/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name }),
  })
  setAuthSession(session)
  return session
}

export async function getSession() {
  return apiFetch('/api/auth/session')
}

export async function fetchIncidents() {
  return apiFetch('/api/incidents')
}

/**
 * Fetch the incidents visible to the currently logged-in agent:
 *   - PENDING incidents with no assignee (claimable queue), AND
 *   - IN_PROGRESS incidents assigned to *this* agent.
 * Cases in progress for OTHER agents are intentionally hidden by the
 * backend and never reach the client.
 */
export async function fetchMyIncidents() {
  return apiFetch('/api/incidents?scope=mine')
}

/**
 * Attempt to claim a PENDING incident for the logged-in agent.
 *
 * Race semantics: the backend takes a row-level `FOR UPDATE` lock on the
 * incident before touching it, so concurrent claim attempts from multiple
 * agents are serialized by Postgres. Exactly one wins; everyone else
 * receives a 409 with `detail.reason === 'ALREADY_CLAIMED'`.
 *
 * Throws an `ApiError` on failure. Inspect `err.status` / `err.detail.reason`
 * to distinguish:
 *   - 409 ALREADY_CLAIMED      -> another agent grabbed it first
 *   - 404 INCIDENT_NOT_FOUND   -> bad id (was deleted?)
 *   - 403 AGENT_NOT_REGISTERED -> session is for a non-agent account
 */
export async function claimIncident(incidentId) {
  return apiFetch(`/api/incidents/${encodeURIComponent(incidentId)}/claim`, {
    method: 'POST',
  })
}

/** Close an IN_PROGRESS case assigned to the logged-in agent (status -> RESOLVED). */
export async function resolveIncident(incidentId) {
  return apiFetch(`/api/incidents/${encodeURIComponent(incidentId)}/resolve`, {
    method: 'POST',
  })
}

export async function processAudio(blob, { caller_name, location }) {
  const form = new FormData()
  form.append('audio', new File([blob], 'incident.webm', { type: 'audio/webm' }))
  form.append('caller_name', caller_name || 'Unknown')
  form.append('location', location || 'Unknown')

  return apiFetch('/api/process-audio', { method: 'POST', body: form })
}

/**
 * Drive the FastAPI /api/triage webhook from the frontend (or anywhere).
 * Pass either a `transcript` (Gemini will fill in the rest) or a fully
 * pre-extracted payload. The new incident will be pushed back to the
 * dashboard via the Supabase Realtime channel within ~100ms.
 */
export async function triageIncident(payload) {
  return apiFetch('/api/triage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export { API_URL }
