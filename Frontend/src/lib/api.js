import { attachAgentToken, supabase } from './supabaseClient'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TOKEN_KEY = 'resqnet_token'
const USER_KEY = 'resqnet_user'

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAuthSession(session) {
  localStorage.setItem(TOKEN_KEY, session.access_token)
  localStorage.setItem(USER_KEY, JSON.stringify(session.user))
  // Propagate JWT to the shared Supabase client so Realtime + PostgREST
  // both authenticate as the freshly-logged-in agent.
  attachAgentToken(session.access_token)
}

export function clearAuthSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  supabase.realtime.setAuth(null)
}

export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  const token = getAuthToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_URL}${path}`, { ...options, headers })
  const data = await res.json().catch(() => ({}))

  if (!res.ok) {
    const msg = data.detail || data.message || `Request failed (${res.status})`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
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
