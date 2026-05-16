import { useState, useEffect, useCallback } from 'react'
import {
  Sun,
  Moon,
  MapPin,
  Loader2,
  User,
  Activity,
  ShieldAlert,
  Flame,
  Clock,
  Radio,
} from 'lucide-react'
import { supabase, attachAgentToken } from '../lib/supabaseClient'
import './AgentDashboard.css'

const THEME_KEY = 'resqnet-theme'

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

function syncPillClass(liveStatus) {
  if (liveStatus === 'live') return 'sync-pill sync-pill--live'
  if (liveStatus === 'error') return 'sync-pill sync-pill--error'
  return 'sync-pill'
}

function syncPillLabel(liveStatus) {
  if (liveStatus === 'live') return 'Live'
  if (liveStatus === 'error') return 'Offline'
  return 'Syncing'
}

/* ─── Theme ──────────────────────────────────────────────── */
function useTheme() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem(THEME_KEY) || 'dark',
  )

  useEffect(() => {
    const root = document.documentElement
    root.classList.remove('dark', 'light')
    root.classList.add(theme)
    localStorage.setItem(THEME_KEY, theme)
  }, [theme])

  const toggle = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))
  return { toggle, isDark: theme === 'dark' }
}

/* ─── Sub-components ─────────────────────────────────────── */

function BrandMark() {
  return (
    <div className="brand-mark">
      <div className="brand-icon" aria-hidden>
        <svg width="15" height="15" viewBox="0 0 14 14" fill="none">
          <path
            d="M1 7 Q2.5 3 4 7 Q5.5 11 7 7 Q8.5 3 10 7 Q11.5 11 13 7"
            stroke="#A8FF3E"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <span className="brand-wordmark">RESQNET</span>
    </div>
  )
}

function ThemeToggleButton({ isDark, onToggle }) {
  return (
    <button
      type="button"
      className="btn-theme"
      onClick={onToggle}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDark ? (
        <Sun className="btn-theme-icon" aria-hidden />
      ) : (
        <Moon className="btn-theme-icon" aria-hidden />
      )}
    </button>
  )
}

function StatsOverviewBar({ incidents }) {
  const medical = incidents.filter(i => i.incident_type === 'MEDICAL').length
  const disaster = incidents.filter(
    i => i.incident_type === 'DISASTER' || !i.incident_type,
  ).length
  const critical = incidents.filter(
    i => urgencyTier(i.urgency_score) === 'critical',
  ).length

  const items = [
    { label: 'Total Pending', value: incidents.length, modifier: 'total' },
    { label: 'Medical', value: medical, modifier: 'medical' },
    { label: 'Disaster', value: disaster, modifier: 'disaster' },
    { label: 'Critical', value: critical, modifier: 'critical' },
  ]

  return (
    <div className="stats-bar">
      {items.map(({ label, value, modifier }) => (
        <div key={label} className={`stat-card stat-card--${modifier}`}>
          <span className="stat-card-label">{label}</span>
          <span className="stat-card-value">{value}</span>
        </div>
      ))}
    </div>
  )
}

function StructuredTags({ data }) {
  const skip = new Set(['location', 'action_items'])
  const entries = Object.entries(data).filter(
    ([k, v]) => !skip.has(k) && v != null && String(v).trim() !== '',
  )

  if (entries.length === 0) return null

  return (
    <div className="tag-container">
      {entries.map(([key, val]) => (
        <span key={key} className="tag-pill">
          <span className="tag-pill-key">{key.replace(/_/g, ' ')}</span>
          <span className="tag-pill-sep">·</span>
          <span>{String(val).slice(0, 48)}</span>
        </span>
      ))}
    </div>
  )
}

function TypeBadge({ isMedical, typeLabel }) {
  if (isMedical) {
    return (
      <span className="badge-medical">
        <span className="badge-icon-wrap">
          <ShieldAlert className="badge-icon" aria-hidden />
        </span>
        {typeLabel}
      </span>
    )
  }

  return (
    <span className="badge-disaster">
      <span className="badge-icon-wrap">
        <Flame className="badge-icon" aria-hidden />
      </span>
      {typeLabel}
    </span>
  )
}

function IncidentCard({ incident, onAccept, accepting }) {
  const structured = parseStructured(incident.structured_data)
  const location = structured.location || 'Location unknown'
  const score = normalizeScore(incident.urgency_score)
  const tier = urgencyTier(incident.urgency_score)
  const isMedical = incident.incident_type === 'MEDICAL'
  const typeLabel = incident.incident_type || 'DISASTER'
  const transcript = incident.transcript || ''

  return (
    <article className={`incident-card incident-card--${tier}`}>
      <header className="incident-card-header">
        <div className="incident-card-header-row">
          <TypeBadge isMedical={isMedical} typeLabel={typeLabel} />
          <div className="urgency-block">
            <p className="urgency-label">Urgency</p>
            <p className="urgency-score">{score}</p>
          </div>
        </div>
      </header>

      <div className="incident-card-body">
        <div className="location-wrapper">
          <div className="location-row">
            <MapPin className="location-icon" aria-hidden />
            <p className="location-text">{location}</p>
          </div>
          <div className="timestamp-row">
            <Clock className="timestamp-icon" aria-hidden />
            <span>{timeAgo(incident.created_at)}</span>
          </div>
        </div>

        {transcript && <p className="incident-transcript">{transcript}</p>}

        <StructuredTags data={structured} />
      </div>

      <footer className="incident-card-footer">
        <button
          type="button"
          className="btn-accept"
          disabled={accepting}
          onClick={() => onAccept(incident)}
        >
          {accepting ? (
            <>
              <Loader2 className="btn-accept-icon" aria-hidden />
              Accepting…
            </>
          ) : (
            'Accept Case'
          )}
        </button>
      </footer>
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

  const user = getUser()
  const agentName = user.name || user.email?.split('@')[0] || 'Agent'
  const initials = agentName
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  const loadPending = useCallback(async () => {
    const { data, error: err } = await supabase
      .from('incidents')
      .select('*, users(name, contact_number)')
      .eq('status', 'PENDING')
      .order('urgency_score', { ascending: false })

    if (err) throw err
    return sortByUrgency(data ?? [])
  }, [])

  useEffect(() => {
    let cancelled = false

    const token = localStorage.getItem('resqnet_token')
    if (token) attachAgentToken(token)

    const channel = supabase
      .channel('schema-db-changes')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'incidents',
          filter: 'status=eq.PENDING',
        },
        payload => {
          const row = payload?.new
          if (!row?.id) return
          setIncidents(prev =>
            sortByUrgency([row, ...prev.filter(i => i.id !== row.id)]),
          )
        },
      )
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'incidents' },
        payload => {
          const row = payload?.new
          if (!row?.id) return
          if (row.status !== 'PENDING') {
            setIncidents(prev => prev.filter(i => i.id !== row.id))
            return
          }
          setIncidents(prev =>
            sortByUrgency([row, ...prev.filter(i => i.id !== row.id)]),
          )
        },
      )
      .on(
        'postgres_changes',
        { event: 'DELETE', schema: 'public', table: 'incidents' },
        payload => {
          const id = payload?.old?.id
          if (!id) return
          setIncidents(prev => prev.filter(i => i.id !== id))
        },
      )
      .subscribe(status => {
        console.log('Supabase Realtime Status changed:', status)
        if (cancelled) return
        if (status === 'SUBSCRIBED') setLiveStatus('live')
        else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT')
          setLiveStatus('error')
        else setLiveStatus('connecting')
      })

    loadPending()
      .then(rows => {
        if (cancelled) return
        setIncidents(prev => {
          const byId = new Map(prev.map(r => [r.id, r]))
          for (const row of rows) byId.set(row.id, row)
          return sortByUrgency([...byId.values()])
        })
        setLoading(false)
      })
      .catch(e => {
        if (cancelled) return
        setError(e.message)
        setLoading(false)
      })

    return () => {
      cancelled = true
      supabase.removeChannel(channel)
    }
  }, [loadPending])

  async function handleAccept(incident) {
    setAcceptingId(incident.id)
    setError(null)
    const { error: err } = await supabase
      .from('incidents')
      .update({ status: 'IN_PROGRESS', agent_id: user.id || null })
      .eq('id', incident.id)
    if (err) setError(err.message)
    setAcceptingId(null)
  }

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div className="dashboard-inner">
          <BrandMark />

          <div className="header-divider" aria-hidden />

          <div className="header-pending">
            <Activity
              className={`header-pending-icon${liveStatus === 'live' ? ' is-live' : ''}`}
              aria-hidden
            />
            <p className="header-pending-label">
              <span className="header-pending-label-short">Pending</span>
              <span className="header-pending-label-full">Active Pending Cases</span>
            </p>
            <p className="header-pending-count">{incidents.length}</p>
          </div>

          <div className="header-actions">
            <div className={syncPillClass(liveStatus)}>
              <Radio className="sync-pill-icon" aria-hidden />
              <span className="sync-pill-text">{syncPillLabel(liveStatus)}</span>
            </div>

            <ThemeToggleButton isDark={isDark} onToggle={toggle} />

            <button
              type="button"
              className="btn-profile"
              onClick={onSignOut}
              title={agentName}
            >
              {initials ? (
                <span className="btn-profile-initials">{initials}</span>
              ) : (
                <User className="btn-profile-icon" aria-hidden />
              )}
            </button>
          </div>
        </div>
      </header>

      <main className="dashboard-main">
        {error && (
          <div className="alert-banner" role="alert">
            {error}
          </div>
        )}

        <section className="stats-section">
          <StatsOverviewBar incidents={incidents} />
        </section>

        {loading ? (
          <div className="state-panel">
            <Loader2 className="state-panel-spinner" aria-hidden />
            <p className="state-panel-title">Loading pending incidents…</p>
          </div>
        ) : incidents.length === 0 ? (
          <div className="state-panel state-panel--empty">
            <Activity className="state-panel-icon" aria-hidden />
            <p className="state-panel-title">No pending cases</p>
            <p className="state-panel-desc">
              New incidents from Telegram will appear here automatically.
            </p>
          </div>
        ) : (
          <div className="incident-grid">
            {incidents.map(incident => (
              <IncidentCard
                key={incident.id}
                incident={incident}
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
