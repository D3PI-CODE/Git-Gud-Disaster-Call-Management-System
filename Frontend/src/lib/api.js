const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TOKEN_KEY = 'resqnet_agent_token'

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAuthSession(session) {
  localStorage.setItem(TOKEN_KEY, session.access_token)
  localStorage.setItem('resqnet_agent_user', JSON.stringify(session.user))
}

export function clearAuthSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem('resqnet_agent_user')
}

export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('resqnet_agent_user') || 'null')
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

export { API_URL }
