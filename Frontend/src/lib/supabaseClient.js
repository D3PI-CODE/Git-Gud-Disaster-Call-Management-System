import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  throw new Error(
    '[ResQNet] Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY in Frontend/.env',
  )
}

const TOKEN_KEY = 'resqnet_auth_token'
const LEGACY_TOKEN_KEY = 'resqnet_token'

function readStoredToken() {
  if (typeof sessionStorage === 'undefined') return null
  return (
    sessionStorage.getItem(TOKEN_KEY) ||
    sessionStorage.getItem(LEGACY_TOKEN_KEY)
  )
}

let agentAccessToken = readStoredToken()

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    persistSession: false,
    autoRefreshToken: false,
  },
  global: {
    fetch: (url, options = {}) => {
      const headers = new Headers(options.headers)
      if (agentAccessToken) {
        headers.set('Authorization', `Bearer ${agentAccessToken}`)
      } else {
        headers.delete('Authorization')
      }
      return fetch(url, { ...options, headers })
    },
  },
})

/** Attach the agent JWT from backend login to REST + Realtime. */
export function attachAgentToken(token) {
  agentAccessToken = token || null
  if (agentAccessToken) {
    supabase.realtime.setAuth(agentAccessToken)
  } else {
    supabase.realtime.setAuth(null)
  }
}

if (agentAccessToken) {
  attachAgentToken(agentAccessToken)
}
