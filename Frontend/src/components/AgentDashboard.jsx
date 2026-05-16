import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { createClient } from '@supabase/supabase-js'
import {
  Sun,
  Moon,
  MapPin,
  Loader2,
  User,
  Stethoscope,
  AlertTriangle,
  Radio,
} from 'lucide-react'

/* ─── Supabase ───────────────────────────────────────────── */
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON = import.meta.env.VITE_SUPABASE_ANON_KEY
const THEME_KEY = 'resqnet-theme'

function makeClient() {
  const token = localStorage.getItem('resqnet_token')
  const client = createClient(SUPABASE_URL, SUPABASE_ANON, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  })
  if (token) client.realtime.setAuth(token)
  return client
}

/* ─── Helpers ────────────────────────────────────────────── */
function parseStructured(raw) {
  if (!raw) return {}
  if (typeof raw === 'object') return raw
  try {
    return JSON.parse(raw)
  } catch {
    return {}
  }
}

function normalizeScore(s) {
  if (s == null || Number.isNaN(Number(s))) return 0
  const n = Number(s)
  return n > 0 && n <= 1 ? Math.round(n * 100) : Math.round(Math.min(100, n))
}

function urgencyTier(score) {
  const n = normalizeScore(score)
  if (n > 80) return 'critical'
  if (n >= 50) return 'high'
  if (n >= 30) return 'medium'
  return 'low'
}

function sortByUrgency(list) {
  return [...list].sort(
    (a, b) => (Number(b.urgency_score) || 0) - (Number(a.urgency_score) || 0),
  )
}

function timeAgo(str) {
  const s = (Date.now() - new Date(str)) / 1000
  if (s < 60) return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

function getUser() {
  try {
    return JSON.parse(localStorage.getItem('resqnet_user') || '{}')
  } catch {
    return {}
  }
}

const URGENCY_BORDER = {
  critical: 'border-t-[#FF3B30]',
  high: 'border-t-[#FF7A00]',
  medium: 'border-t-[#FFBB00]',
  low: 'border-t-[#3D8BFF]',
}

/* ─── Theme ──────────────────────────────────────────────── */
function useTheme() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem(THEME_KEY) || 'dark',
  )

  useEffect(() => {
    document.documentElement.className = theme
    localStorage.setItem(THEME_KEY, theme)
  }, [theme])

  const toggle = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))
  return { toggle, isDark: theme === 'dark' }
}

/* ─── Sub-components ─────────────────────────────────────── */

function BrandMark({ isDark }) {
  return (
    <div className="flex shrink-0 items-center gap-2">
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${
          isDark
            ? 'border-[#A8FF3E]/35 bg-[#A8FF3E]/10'
            : 'border-[#84CC16]/40 bg-[#84CC16]/10'
        }`}
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
          <path
            d="M1 7 Q2.5 3 4 7 Q5.5 11 7 7 Q8.5 3 10 7 Q11.5 11 13 7"
            stroke="#A8FF3E"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <span
        className={`hidden font-['Chakra_Petch'] text-sm font-bold tracking-[0.18em] sm:inline ${
          isDark ? 'text-[#E0E0E0]' : 'text-[#1E293B]'
        }`}
      >
        RESQNET
      </span>
    </div>
  )
}

function ThemeToggleButton({ isDark, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border transition-all duration-200 ${
        isDark
          ? 'border-white/10 bg-[#2C2C2C] text-[#E0E0E0]/70 hover:border-[#A8FF3E]/30 hover:bg-[#A8FF3E]/10 hover:text-[#A8FF3E]'
          : 'border-slate-200 bg-white text-slate-500 hover:border-[#84CC16]/40 hover:bg-[#84CC16]/10 hover:text-[#65A30D]'
      }`}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  )
}

function StatsOverviewBar({ incidents, isDark }) {
  const medical = incidents.filter(i => i.incident_type === 'MEDICAL').length
  const disaster = incidents.filter(
    i => i.incident_type === 'DISASTER' || !i.incident_type,
  ).length
  const critical = incidents.filter(
    i => urgencyTier(i.urgency_score) === 'critical',
  ).length

  const items = [
    { label: 'Total Pending', value: incidents.length },
    { label: 'Medical', value: medical },
    { label: 'Disaster', value: disaster },
    { label: 'Critical', value: critical },
  ]

  return (
    <div
      className={`grid grid-cols-2 gap-4 rounded-lg border p-4 sm:grid-cols-4 sm:gap-6 sm:p-6 ${
        isDark
          ? 'border-white/[0.06] bg-[#2C2C2C]'
          : 'border-slate-200 bg-white shadow-sm'
      }`}
    >
      {items.map(({ label, value }) => (
        <div key={label} className="flex min-w-0 flex-col gap-2 px-1 sm:px-2">
          <span
            className={`font-['Chakra_Petch'] text-[10px] font-semibold uppercase tracking-[0.14em] ${
              isDark ? 'text-[#E0E0E0]/50' : 'text-slate-500'
            }`}
          >
            {label}
          </span>
          <span
            className={`font-['Chakra_Petch'] text-2xl font-bold tabular-nums tracking-tight ${
              isDark ? 'text-[#E0E0E0]' : 'text-[#1E293B]'
            }`}
          >
            {value}
          </span>
        </div>
      ))}
    </div>
  )
}

function StructuredTags({ data, isDark }) {
  const skip = new Set(['location', 'action_items'])
  const entries = Object.entries(data).filter(
    ([k, v]) => !skip.has(k) && v != null && String(v).trim() !== '',
  )

  if (entries.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([key, val]) => (
        <span
          key={key}
          className={`rounded-md px-2 py-0.5 font-['JetBrains_Mono'] text-[10px] tracking-wide ${
            isDark
              ? 'border border-white/[0.08] bg-[#1A1A1A] text-[#E0E0E0]/70'
              : 'border border-slate-200 bg-slate-50 text-slate-600'
          }`}
        >
          {key.replace(/_/g, ' ')}: {String(val).slice(0, 40)}
        </span>
      ))}
    </div>
  )
}

function IncidentCard({ incident, isDark, onAccept, accepting }) {
  const structured = parseStructured(incident.structured_data)
  const location = structured.location || 'Location unknown'
  const score = normalizeScore(incident.urgency_score)
  const tier = urgencyTier(incident.urgency_score)
  const isMedical = incident.incident_type === 'MEDICAL'
  const typeLabel = incident.incident_type || 'DISASTER'
  const transcript = incident.transcript || ''

  return (
    <article
      className={`flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-t-4 transition-shadow duration-200 ${URGENCY_BORDER[tier]} ${
        tier === 'critical' ? 'animate-[urgency-pulse_2s_ease-in-out_infinite]' : ''
      } ${
        isDark
          ? 'border-white/[0.06] bg-[#2C2C2C] hover:shadow-[0_8px_32px_rgba(0,0,0,0.35)]'
          : 'border-slate-200 bg-white shadow-sm hover:shadow-md'
      }`}
    >
      <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 sm:p-6">
        <div className="flex items-start justify-between gap-3">
          <span
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 font-['Chakra_Petch'] text-[10px] font-bold uppercase tracking-[0.12em] ${
              isMedical
                ? isDark
                  ? 'bg-[#3D8BFF]/15 text-[#6BA3FF] ring-1 ring-[#3D8BFF]/25'
                  : 'bg-blue-50 text-blue-700 ring-1 ring-blue-200'
                : isDark
                  ? 'bg-[#FF7A00]/15 text-[#FF9F4D] ring-1 ring-[#FF7A00]/25'
                  : 'bg-orange-50 text-orange-700 ring-1 ring-orange-200'
            }`}
          >
            {isMedical ? (
              <Stethoscope className="h-3 w-3" />
            ) : (
              <AlertTriangle className="h-3 w-3" />
            )}
            {typeLabel}
          </span>
          <div className="shrink-0 text-right">
            <p
              className={`font-['Chakra_Petch'] text-[10px] font-semibold uppercase tracking-[0.14em] ${
                isDark ? 'text-[#E0E0E0]/45' : 'text-slate-400'
              }`}
            >
              Urgency
            </p>
            <p
              className={`font-['Chakra_Petch'] text-2xl font-bold tabular-nums leading-none sm:text-3xl ${
                tier === 'critical'
                  ? 'text-[#FF3B30]'
                  : tier === 'high'
                    ? 'text-[#FF7A00]'
                    : tier === 'medium'
                      ? 'text-[#FFBB00]'
                      : isDark
                        ? 'text-[#3D8BFF]'
                        : 'text-blue-600'
              }`}
            >
              {score}
            </p>
          </div>
        </div>

        <div className="space-y-1">
          <div
            className={`flex min-w-0 items-start gap-2 text-sm ${
              isDark ? 'text-[#E0E0E0]/80' : 'text-slate-600'
            }`}
          >
            <MapPin
              className={`mt-0.5 h-4 w-4 shrink-0 ${
                isDark ? 'text-[#A8FF3E]/80' : 'text-[#65A30D]'
              }`}
            />
            <span className="min-w-0 flex-1 break-words font-['Outfit'] font-medium leading-snug">
              {location}
            </span>
          </div>
          <p
            className={`pl-6 font-['JetBrains_Mono'] text-[10px] ${
              isDark ? 'text-[#E0E0E0]/40' : 'text-slate-400'
            }`}
          >
            {timeAgo(incident.created_at)}
          </p>
        </div>

        {transcript && (
          <p
            className={`line-clamp-3 font-['Outfit'] text-sm leading-relaxed ${
              isDark ? 'text-[#E0E0E0]/65' : 'text-slate-600'
            }`}
          >
            {transcript}
          </p>
        )}

        <StructuredTags data={structured} isDark={isDark} />
      </div>

      <div className={`border-t p-4 ${isDark ? 'border-white/[0.06]' : 'border-slate-100'}`}>
        <button
          type="button"
          disabled={accepting}
          onClick={() => onAccept(incident)}
          className={`flex w-full items-center justify-center gap-2 rounded-lg border px-4 py-3 font-['Chakra_Petch'] text-[11px] font-bold uppercase tracking-[0.2em] transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-30 ${
            isDark
              ? 'border-[#A8FF3E]/30 bg-[#A8FF3E]/10 text-[#A8FF3E] hover:border-[#A8FF3E] hover:bg-[#A8FF3E] hover:text-[#1A1A1A] hover:shadow-[0_4px_24px_rgba(168,255,62,0.2)]'
              : 'border-[#84CC16]/40 bg-[#84CC16]/10 text-[#65A30D] hover:border-[#84CC16] hover:bg-[#84CC16] hover:text-white hover:shadow-[0_4px_24px_rgba(132,204,22,0.25)]'
          }`}
        >
          {accepting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Accepting…
            </>
          ) : (
            'Accept Case'
          )}
        </button>
      </div>
    </article>
  )
}

/* ─── Main dashboard ───────────────────────────────────────── */
export default function AgentDashboard({ onSignOut }) {
  const { toggle, isDark } = useTheme()
  const [incidents, setIncidents] = useState([])
  const [acceptingId, setAcceptingId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [liveStatus, setLiveStatus] = useState('connecting')
  const supaRef = useRef(null)

  const user = getUser()
  const agentName = user.name || user.email?.split('@')[0] || 'Agent'
  const initials = agentName
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  const loadPending = useCallback(async client => {
    const { data, error: err } = await client
      .from('incidents')
      .select('*, users(name, contact_number)')
      .eq('status', 'PENDING')
      .order('urgency_score', { ascending: false })

    if (err) throw err
    return sortByUrgency(data ?? [])
  }, [])

  useEffect(() => {
    let cancelled = false
    let channel = null

    async function init() {
      try {
        const client = makeClient()
        supaRef.current = client

        const pending = await loadPending(client)
        if (!cancelled) {
          setIncidents(pending)
          setLoading(false)
        }

        channel = client
          .channel('agent-dashboard-incidents')
          .on(
            'postgres_changes',
            { event: 'INSERT', schema: 'public', table: 'incidents' },
            payload => {
              const row = payload.new
              if (row?.status !== 'PENDING') return
              setIncidents(prev =>
                sortByUrgency([row, ...prev.filter(i => i.id !== row.id)]),
              )
            },
          )
          .on(
            'postgres_changes',
            { event: 'UPDATE', schema: 'public', table: 'incidents' },
            payload => {
              const row = payload.new
              if (!row) return
              if (row.status !== 'PENDING') {
                setIncidents(prev => prev.filter(i => i.id !== row.id))
                return
              }
              setIncidents(prev =>
                sortByUrgency([row, ...prev.filter(i => i.id !== row.id)]),
              )
            },
          )
          .subscribe(status => {
            if (!cancelled) {
              setLiveStatus(status === 'SUBSCRIBED' ? 'live' : 'connecting')
            }
          })
      } catch (e) {
        if (!cancelled) {
          setError(e.message)
          setLoading(false)
        }
      }
    }

    init()
    return () => {
      cancelled = true
      if (channel && supaRef.current) {
        supaRef.current.removeChannel(channel)
      }
    }
  }, [loadPending])

  async function handleAccept(incident) {
    const client = supaRef.current
    if (!client) return
    setAcceptingId(incident.id)
    setError(null)
    const { error: err } = await client
      .from('incidents')
      .update({ status: 'IN_PROGRESS', agent_id: user.id || null })
      .eq('id', incident.id)
    if (err) setError(err.message)
    setAcceptingId(null)
  }

  const shell = useMemo(
    () =>
      isDark
        ? 'bg-[#1A1A1A] text-[#E0E0E0]'
        : 'bg-[#F8FAFC] text-[#1E293B]',
    [isDark],
  )

  return (
    <div className={`flex min-h-screen flex-col font-['Outfit'] antialiased ${shell}`}>
      <header
        className={`fixed inset-x-0 top-0 z-50 border-b ${
          isDark
            ? 'border-white/[0.06] bg-[#1A1A1A]/95 backdrop-blur-md'
            : 'border-slate-200 bg-[#F8FAFC]/95 backdrop-blur-md'
        }`}
      >
        <div className="mx-auto flex h-16 w-full max-w-[1600px] items-center gap-3 px-4 sm:gap-4 sm:px-6 lg:px-8">
          <BrandMark isDark={isDark} />

          <div
            className={`hidden h-6 w-px shrink-0 md:block ${
              isDark ? 'bg-white/10' : 'bg-slate-200'
            }`}
          />

          <div className="flex min-w-0 flex-1 items-baseline gap-2 overflow-hidden sm:gap-3">
            <p
              className={`truncate font-['Chakra_Petch'] text-[10px] font-semibold uppercase tracking-[0.14em] ${
                isDark ? 'text-[#E0E0E0]/50' : 'text-slate-500'
              }`}
            >
              <span className="hidden sm:inline">Active Pending Cases</span>
              <span className="sm:hidden">Pending</span>
            </p>
            <p
              className={`shrink-0 font-['Chakra_Petch'] text-xl font-bold tabular-nums ${
                isDark ? 'text-[#E0E0E0]' : 'text-[#1E293B]'
              }`}
            >
              {incidents.length}
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            <div
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1.5 font-['Chakra_Petch'] text-[9px] font-semibold uppercase tracking-[0.14em] sm:gap-2 sm:px-3 ${
                liveStatus === 'live'
                  ? isDark
                    ? 'border border-[#34C759]/30 bg-[#34C759]/10 text-[#34C759]'
                    : 'border border-emerald-200 bg-emerald-50 text-emerald-700'
                  : isDark
                    ? 'border border-white/10 bg-[#2C2C2C] text-[#E0E0E0]/40'
                    : 'border border-slate-200 bg-white text-slate-400'
              }`}
            >
              <Radio className="h-3 w-3 shrink-0" />
              <span className="hidden min-[420px]:inline">
                {liveStatus === 'live' ? 'Live' : 'Syncing'}
              </span>
            </div>

            <ThemeToggleButton isDark={isDark} onToggle={toggle} />

            <button
              type="button"
              onClick={onSignOut}
              title={agentName}
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border transition-all duration-200 ${
                isDark
                  ? 'border-white/10 bg-[#2C2C2C] text-[#E0E0E0]/80 hover:border-white/20'
                  : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
              }`}
            >
              {initials ? (
                <span className="font-['Chakra_Petch'] text-[10px] font-bold">
                  {initials}
                </span>
              ) : (
                <User className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col px-4 pb-8 pt-20 sm:px-6 sm:pb-10 lg:px-8">
        {error && (
          <div
            className={`mb-6 rounded-lg border px-4 py-3 font-['Outfit'] text-sm ${
              isDark
                ? 'border-[#FF3B30]/30 bg-[#FF3B30]/10 text-[#FF6B63]'
                : 'border-red-200 bg-red-50 text-red-700'
            }`}
            role="alert"
          >
            {error}
          </div>
        )}

        <section className="mb-6 sm:mb-8">
          <StatsOverviewBar incidents={incidents} isDark={isDark} />
        </section>

        {loading ? (
          <div
            className={`flex min-h-[min(24rem,calc(100vh-14rem))] flex-col items-center justify-center gap-4 rounded-lg border px-6 py-16 ${
              isDark
                ? 'border-white/[0.06] bg-[#2C2C2C]'
                : 'border-slate-200 bg-white'
            }`}
          >
            <Loader2
              className={`h-8 w-8 animate-spin ${
                isDark ? 'text-[#A8FF3E]' : 'text-[#65A30D]'
              }`}
            />
            <p
              className={`font-['Chakra_Petch'] text-xs font-semibold uppercase tracking-[0.14em] ${
                isDark ? 'text-[#E0E0E0]/50' : 'text-slate-500'
              }`}
            >
              Loading pending incidents…
            </p>
          </div>
        ) : incidents.length === 0 ? (
          <div
            className={`flex min-h-[min(24rem,calc(100vh-14rem))] flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-16 text-center ${
              isDark
                ? 'border-white/10 bg-[#2C2C2C]/50'
                : 'border-slate-300 bg-white'
            }`}
          >
            <p
              className={`font-['Chakra_Petch'] text-sm font-bold tracking-wide ${
                isDark ? 'text-[#E0E0E0]/60' : 'text-slate-500'
              }`}
            >
              No pending cases
            </p>
            <p
              className={`max-w-sm font-['Outfit'] text-sm ${
                isDark ? 'text-[#E0E0E0]/40' : 'text-slate-400'
              }`}
            >
              New incidents from Telegram will appear here automatically.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:gap-6 md:grid-cols-2 xl:grid-cols-3">
            {incidents.map(incident => (
              <IncidentCard
                key={incident.id}
                incident={incident}
                isDark={isDark}
                onAccept={handleAccept}
                accepting={acceptingId === incident.id}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
