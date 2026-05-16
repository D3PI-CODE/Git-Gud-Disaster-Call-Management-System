import { useCallback, useEffect, useRef, useState } from 'react'
import { createClient } from '@supabase/supabase-js'
import {
  Loader2,
  MapPin,
  User,
  AlertTriangle,
  Stethoscope,
  Activity,
} from 'lucide-react'

/* ── Supabase ───────────────────────────────────────────────────────── */

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY
const DUMMY_AGENT_ID = '00000000-0000-4000-a000-000000000001'

function createSupabaseClient() {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    throw new Error('[ResQNet] Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY')
  }

  const token = localStorage.getItem('resqnet_token')
  const client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  })

  if (token) client.realtime.setAuth(token)
  return client
}

/* ── Helpers ────────────────────────────────────────────────────────── */

function normalizeUrgency(score) {
  if (score == null || Number.isNaN(Number(score))) return 0
  const n = Number(score)
  if (n > 0 && n <= 1) return Math.round(n * 100)
  return Math.round(Math.min(100, Math.max(0, n)))
}

function sortByUrgency(list) {
  return [...list].sort(
    (a, b) => normalizeUrgency(b.urgency_score) - normalizeUrgency(a.urgency_score)
  )
}

function parseStructuredData(raw) {
  if (!raw) return {}
  if (typeof raw === 'object') return raw
  try {
    return JSON.parse(raw)
  } catch {
    return {}
  }
}

function getAgentDisplayName() {
  try {
    const user = JSON.parse(localStorage.getItem('resqnet_user') || '{}')
    return user?.name || user?.email?.split('@')[0] || 'Agent'
  } catch {
    return 'Agent'
  }
}

function getInitials(name) {
  return name
    .split(/\s+/)
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

const STRUCTURED_SKIP = new Set(['location', 'caller_name'])

function urgencyTier(score) {
  const n = normalizeUrgency(score)
  if (n > 85) return 'critical'
  if (n >= 50) return 'warning'
  return 'muted'
}

const TIER_BORDER = {
  critical: 'border-t-4 border-t-red-500',
  warning: 'border-t-4 border-t-amber-500',
  muted: 'border-t-4 border-t-slate-500',
}

const TIER_SCORE = {
  critical: 'text-red-400',
  warning: 'text-amber-400',
  muted: 'text-slate-400',
}

/* ── Incident card ──────────────────────────────────────────────────── */

function PendingIncidentCard({ incident, onAccept, accepting }) {
  const structured = parseStructuredData(incident.structured_data)
  const location = structured.location || 'Location unknown'
  const urgency = normalizeUrgency(incident.urgency_score)
  const tier = urgencyTier(incident.urgency_score)
  const isMedical = incident.incident_type === 'MEDICAL'

  const detailEntries = Object.entries(structured).filter(
    ([key, val]) =>
      !STRUCTURED_SKIP.has(key) &&
      val != null &&
      String(val).trim() !== ''
  )

  return (
    <article
      className={`flex flex-col overflow-hidden rounded-lg border border-gray-700 bg-gray-800 shadow-lg ${TIER_BORDER[tier]}`}
    >
      <div className="flex flex-1 flex-col p-6">
        <div className="mb-4 flex items-start justify-between gap-3">
          <span
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${
              isMedical
                ? 'bg-blue-500/15 text-blue-400 ring-1 ring-blue-500/30'
                : 'bg-orange-500/15 text-orange-400 ring-1 ring-orange-500/30'
            }`}
          >
            {isMedical ? (
              <Stethoscope className="h-3.5 w-3.5" aria-hidden />
            ) : (
              <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
            )}
            {incident.incident_type || 'DISASTER'}
          </span>

          <div className="text-right">
            <p className="text-[10px] font-medium uppercase tracking-wider text-gray-500">
              Urgency
            </p>
            <p className={`text-4xl font-bold tabular-nums leading-none ${TIER_SCORE[tier]}`}>
              {urgency}
            </p>
          </div>
        </div>

        <div className="mb-4 flex items-start gap-2 rounded-md bg-gray-900/60 p-3 ring-1 ring-gray-700">
          <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-gray-300" aria-hidden />
          <p className="text-sm font-medium leading-snug text-gray-100">{location}</p>
        </div>

        {incident.transcript && (
          <p className="mb-4 line-clamp-2 text-sm italic leading-relaxed text-gray-400">
            {incident.transcript}
          </p>
        )}

        {detailEntries.length > 0 && (
          <div className="mb-5 flex flex-wrap gap-2">
            {detailEntries.map(([key, val]) => (
              <span
                key={key}
                className="rounded bg-gray-700 px-2 py-1 text-xs text-gray-200"
                title={key.replace(/_/g, ' ')}
              >
                <span className="text-gray-500">{key.replace(/_/g, ' ')}:</span>{' '}
                {String(val)}
              </span>
            ))}
          </div>
        )}

        <div className="mt-auto">
          <button
            type="button"
            onClick={() => onAccept(incident)}
            disabled={accepting}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-gray-100 px-4 py-3 text-sm font-semibold text-gray-900 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {accepting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                Assigning...
              </>
            ) : (
              'Accept Case'
            )}
          </button>
        </div>
      </div>
    </article>
  )
}

/* ── Agent dashboard ────────────────────────────────────────────────── */

export default function AgentDashboard({ onSignOut }) {
  const [incidents, setIncidents] = useState([])
  const [acceptingId, setAcceptingId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [liveStatus, setLiveStatus] = useState('connecting')
  const supabaseRef = useRef(null)

  const agentName = getAgentDisplayName()
  const agentInitials = getInitials(agentName)

  const fetchPending = useCallback(async client => {
    const { data, error: fetchError } = await client
      .from('incidents')
      .select('*')
      .eq('status', 'PENDING')
      .order('urgency_score', { ascending: false })

    if (fetchError) throw fetchError
    return sortByUrgency(data ?? [])
  }, [])

  useEffect(() => {
    let cancelled = false
    let channel = null

    async function init() {
      try {
        const client = createSupabaseClient()
        supabaseRef.current = client

        const pending = await fetchPending(client)
        if (!cancelled) {
          setIncidents(pending)
          setLoading(false)
          setError(null)
        }

        channel = client
          .channel('resqnet-pending-incidents')
          .on(
            'postgres_changes',
            { event: 'INSERT', schema: 'public', table: 'incidents' },
            payload => {
              const row = payload.new
              if (row?.status !== 'PENDING') return
              setIncidents(prev =>
                sortByUrgency([row, ...prev.filter(i => i.id !== row.id)])
              )
            }
          )
          .on(
            'postgres_changes',
            { event: 'UPDATE', schema: 'public', table: 'incidents' },
            payload => {
              const row = payload.new
              if (!row) return
              if (row.status !== 'PENDING') {
                setIncidents(prev => prev.filter(i => i.id !== row.id))
              } else {
                setIncidents(prev =>
                  sortByUrgency(
                    prev.some(i => i.id === row.id)
                      ? prev.map(i => (i.id === row.id ? row : i))
                      : [row, ...prev]
                  )
                )
              }
            }
          )
          .subscribe(status => {
            if (!cancelled) {
              setLiveStatus(status === 'SUBSCRIBED' ? 'live' : 'connecting')
            }
          })
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Failed to load incidents')
          setLoading(false)
          setLiveStatus('offline')
        }
      }
    }

    init()

    return () => {
      cancelled = true
      if (channel && supabaseRef.current) {
        supabaseRef.current.removeChannel(channel)
      }
    }
  }, [fetchPending])

  async function handleAccept(incident) {
    const client = supabaseRef.current
    if (!client) return

    setAcceptingId(incident.id)
    setError(null)

    const { error: updateError } = await client
      .from('incidents')
      .update({
        status: 'IN_PROGRESS',
        agent_id: DUMMY_AGENT_ID,
      })
      .eq('id', incident.id)

    if (updateError) {
      setError(updateError.message)
    }

    setAcceptingId(null)
  }

  return (
    <div className="flex min-h-screen flex-col bg-gray-900 text-gray-100">
      <header className="sticky top-0 z-20 border-b border-gray-800 bg-gray-900/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-800 ring-1 ring-gray-700">
              <Activity className="h-5 w-5 text-gray-200" aria-hidden />
            </div>
            <h1 className="text-lg font-bold tracking-tight text-white">ResQNet</h1>
          </div>

          <div className="flex items-center gap-4 sm:gap-6">
            <div className="hidden items-center gap-2 text-xs text-gray-500 sm:flex">
              <span
                className={`h-2 w-2 rounded-full ${
                  liveStatus === 'live' ? 'bg-emerald-500' : 'bg-gray-600'
                }`}
              />
              {liveStatus === 'live' ? 'Live' : 'Connecting'}
            </div>

            <div className="text-right">
              <p className="text-[10px] font-medium uppercase tracking-wider text-gray-500">
                Active pending cases
              </p>
              <p className="text-2xl font-bold tabular-nums text-white">{incidents.length}</p>
            </div>

            <div
              className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-800 text-sm font-semibold text-gray-200 ring-1 ring-gray-700"
              title={agentName}
            >
              {agentInitials || <User className="h-4 w-4 text-gray-400" aria-hidden />}
            </div>

            {onSignOut && (
              <button
                type="button"
                onClick={onSignOut}
                className="rounded-lg border border-gray-700 px-3 py-2 text-xs font-medium text-gray-400 transition-colors hover:border-gray-600 hover:text-gray-200"
              >
                Sign out
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
          {error && (
            <div
              className="mb-6 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300"
              role="alert"
            >
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-24 text-gray-500">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" aria-hidden />
              <p className="text-sm">Loading pending cases…</p>
            </div>
          ) : incidents.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-gray-700 bg-gray-800/50 px-6 py-20 text-center">
              <Activity className="mb-3 h-10 w-10 text-gray-600" aria-hidden />
              <p className="text-base font-semibold text-gray-200">No pending cases</p>
              <p className="mt-2 max-w-md text-sm text-gray-500">
                New incidents from Telegram will appear here automatically when they are parsed
                and queued for triage.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
              {incidents.map(incident => (
                <PendingIncidentCard
                  key={incident.id}
                  incident={incident}
                  onAccept={handleAccept}
                  accepting={acceptingId === incident.id}
                />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
