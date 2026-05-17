import { useState, useEffect, useCallback, useRef } from 'react'
import {
  MapPin,
  Loader2,
  User,
  Activity,
  ShieldAlert,
  Flame,
  Clock,
  Radio,
  LogOut,
  ChevronDown,
  CheckCircle,
} from 'lucide-react'
import { supabase, attachAgentToken } from '../lib/supabaseClient'
import {
  getAuthToken,
  getCurrentAgentId,
  getStoredUser,
  claimIncident,
  resolveIncident,
  ApiError,
} from '../lib/api'
import './AgentDashboard.css'

const AGENT_LOCATION_KEY = 'resqnet_agent_location'
const RESOLVE_SUCCESS_MS = 350
const RESOLVE_EXIT_MS = 520

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

function isUnassignedPending(row) {
  return row?.status === 'PENDING' && row.agent_id == null
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

/* ─── Lock permanent dark theme on dashboard mount ───────── */
function usePermanentDark() {
  useEffect(() => {
    const root = document.documentElement
    root.classList.remove('light')
    root.classList.add('dark')
  }, [])
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

function AvatarMenu({ agentName, initials, onSignOut }) {
  const [isOpen, setIsOpen] = useState(false)
  const [activeLocation, setActiveLocation] = useState(
    () => localStorage.getItem(AGENT_LOCATION_KEY) || 'Colombo, Western Province',
  )
  const [locationDraft, setLocationDraft] = useState(activeLocation)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!isOpen) return

    function handlePointerDown(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }

    function handleEscape(e) {
      if (e.key === 'Escape') setIsOpen(false)
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  function toggleMenu() {
    setIsOpen(prev => {
      if (!prev) setLocationDraft(activeLocation)
      return !prev
    })
  }

  function saveLocation() {
    const trimmed = locationDraft.trim()
    if (!trimmed) return
    setActiveLocation(trimmed)
    localStorage.setItem(AGENT_LOCATION_KEY, trimmed)
  }

  function handleLogout() {
    setIsOpen(false)
    onSignOut()
  }

  return (
    <div className="avatar-menu" ref={menuRef}>
      <button
        type="button"
        className={`avatar-trigger${isOpen ? ' is-open' : ''}`}
        onClick={toggleMenu}
        aria-expanded={isOpen}
        aria-haspopup="true"
        title={agentName}
      >
        {initials ? (
          <span className="avatar-trigger-initials">{initials}</span>
        ) : (
          <User className="avatar-trigger-icon" aria-hidden />
        )}
        <ChevronDown className="avatar-trigger-chevron" aria-hidden />
      </button>

      <div
        className={`avatar-dropdown-menu${isOpen ? ' is-open' : ''}`}
        role="menu"
        aria-hidden={!isOpen}
      >
        <div className="avatar-dropdown-header">
          <p className="avatar-dropdown-name">{agentName}</p>
          <p className="avatar-dropdown-role">Field Agent</p>
        </div>

        <div className="avatar-dropdown-divider" />

        <div className="avatar-dropdown-location">
          <label className="avatar-dropdown-location-label" htmlFor="agent-location-input">
            <MapPin className="avatar-dropdown-row-icon" aria-hidden />
            Change Active Location
          </label>
          <div className="avatar-dropdown-location-row">
            <input
              id="agent-location-input"
              type="text"
              className="avatar-dropdown-input"
              value={locationDraft}
              onChange={e => setLocationDraft(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') saveLocation()
              }}
              placeholder="e.g. Colombo, Western Province"
            />
            <button type="button" className="avatar-dropdown-save" onClick={saveLocation}>
              Save
            </button>
          </div>
          <p className="avatar-dropdown-location-current">{activeLocation}</p>
        </div>

        <div className="avatar-dropdown-divider" />

        <button type="button" className="avatar-dropdown-item" onClick={handleLogout} role="menuitem">
          <LogOut className="avatar-dropdown-row-icon" aria-hidden />
          Log Out
        </button>
      </div>
    </div>
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
      {items.map(({ label, value, modifier }, index) => (
        <div
          key={label}
          className={`stat-card stat-card--${modifier}`}
          style={{ animationDelay: `${index * 0.08}s` }}
        >
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

function IncidentCard({
  incident,
  variant = 'queue',
  onAccept,
  accepting,
  onResolve,
  resolving,
  resolveSuccess,
  exiting,
  staggerIndex,
}) {
  const structured = parseStructured(incident.structured_data)
  const location = structured.location || 'Location unknown'
  const score = normalizeScore(incident.urgency_score)
  const tier = urgencyTier(incident.urgency_score)
  const isMedical = incident.incident_type === 'MEDICAL'
  const typeLabel = incident.incident_type || 'DISASTER'
  const transcript = incident.transcript || ''
  const isActive = variant === 'active'

  return (
    <article
      className={`incident-card incident-card--${tier}${resolveSuccess ? ' incident-card--resolve-success' : ''}${exiting ? ' incident-card--exit' : ''}`}
      style={{ animationDelay: `${Math.min(staggerIndex, 12) * 0.06}s` }}
    >
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
        {isActive ? (
          <button
            type="button"
            className={`btn-resolve${resolveSuccess ? ' btn-resolve--success' : ''}`}
            disabled={resolving || resolveSuccess || exiting}
            onClick={() => onResolve?.(incident)}
          >
            {resolveSuccess ? (
              <>
                <CheckCircle className="btn-resolve-icon" aria-hidden />
                Case Resolved
              </>
            ) : resolving ? (
              <>
                <Loader2 className="btn-resolve-icon btn-resolve-icon--spin" aria-hidden />
                Resolving…
              </>
            ) : (
              'Resolve Case'
            )}
          </button>
        ) : (
          <button
            type="button"
            className="btn-accept"
            disabled={accepting}
            onClick={() => onAccept?.(incident)}
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
        )}
      </footer>
    </article>
  )
}

/* ─── Main dashboard ───────────────────────────────────────── */
export default function AgentDashboard({ onSignOut }) {
  usePermanentDark()

  const [pendingIncidents, setPendingIncidents] = useState([])
  const [myActiveIncidents, setMyActiveIncidents] = useState([])
  const [activePanel, setActivePanel] = useState('queue')
  const [acceptingId, setAcceptingId] = useState(null)
  const [resolvingId, setResolvingId] = useState(null)
  const [resolveFlashIds, setResolveFlashIds] = useState(() => new Set())
  const [exitingIds, setExitingIds] = useState(() => new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [liveStatus, setLiveStatus] = useState('connecting')

  const user = getStoredUser() || {}
  const currentAgentId = getCurrentAgentId()
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
      .is('agent_id', null)
      .order('urgency_score', { ascending: false })

    if (err) throw err
    return sortByUrgency(data ?? [])
  }, [])

  const loadMyActive = useCallback(async () => {
    const agentId = getCurrentAgentId()
    if (!agentId) return []

    const { data, error: err } = await supabase
      .from('incidents')
      .select('*, users(name, contact_number)')
      .eq('status', 'IN_PROGRESS')
      .eq('agent_id', agentId)
      .order('urgency_score', { ascending: false })

    if (err) throw err
    return sortByUrgency(data ?? [])
  }, [])

  useEffect(() => {
    let cancelled = false
    const agentId = getCurrentAgentId()

    const token = getAuthToken()
    if (token) attachAgentToken(token)

    // #region agent log
    fetch('http://127.0.0.1:7501/ingest/c12efe83-6414-4913-b137-e3a0c8e0b6e5', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Debug-Session-Id': '1a86c0',
      },
      body: JSON.stringify({
        sessionId: '1a86c0',
        hypothesisId: 'H3-H4',
        location: 'AgentDashboard.jsx:mount',
        message: 'dashboard_mount_auth',
        data: {
          hasToken: Boolean(token),
          hasAgentId: Boolean(agentId),
          tokenKey: token
            ? sessionStorage.getItem('resqnet_auth_token')
              ? 'resqnet_auth_token'
              : 'legacy'
            : 'none',
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {})
    // #endregion

    function removeFromBoth(id) {
      setPendingIncidents(prev => prev.filter(i => i.id !== id))
      setMyActiveIncidents(prev => prev.filter(i => i.id !== id))
    }

    function routeUpdate(row) {
      if (!row?.id) return

      if (row.status === 'IN_PROGRESS') {
        setPendingIncidents(prev => prev.filter(i => i.id !== row.id))
        if (row.agent_id === agentId) {
          setMyActiveIncidents(prev =>
            sortByUrgency([row, ...prev.filter(i => i.id !== row.id)]),
          )
        } else {
          setMyActiveIncidents(prev => prev.filter(i => i.id !== row.id))
        }
        return
      }

      if (row.status === 'RESOLVED') {
        removeFromBoth(row.id)
        return
      }

      if (isUnassignedPending(row)) {
        setMyActiveIncidents(prev => prev.filter(i => i.id !== row.id))
        setPendingIncidents(prev =>
          sortByUrgency([row, ...prev.filter(i => i.id !== row.id)]),
        )
        return
      }

      removeFromBoth(row.id)
    }

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
          if (!row?.id || !isUnassignedPending(row)) return
          setPendingIncidents(prev =>
            sortByUrgency([row, ...prev.filter(i => i.id !== row.id)]),
          )
        },
      )
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'incidents' },
        payload => {
          routeUpdate(payload?.new)
        },
      )
      .on(
        'postgres_changes',
        { event: 'DELETE', schema: 'public', table: 'incidents' },
        payload => {
          const id = payload?.old?.id
          if (!id) return
          removeFromBoth(id)
        },
      )
      .subscribe(status => {
        if (cancelled) return
        // #region agent log
        fetch('http://127.0.0.1:7501/ingest/c12efe83-6414-4913-b137-e3a0c8e0b6e5', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Debug-Session-Id': '1a86c0',
          },
          body: JSON.stringify({
            sessionId: '1a86c0',
            hypothesisId: 'H4',
            location: 'AgentDashboard.jsx:realtime',
            message: 'realtime_status',
            data: { status },
            timestamp: Date.now(),
          }),
        }).catch(() => {})
        // #endregion
        if (status === 'SUBSCRIBED') setLiveStatus('live')
        else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT')
          setLiveStatus('error')
        else setLiveStatus('connecting')
      })

    Promise.all([loadPending(), loadMyActive()])
      .then(([pendingRows, activeRows]) => {
        if (cancelled) return
        setPendingIncidents(pendingRows)
        setMyActiveIncidents(activeRows)
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
  }, [loadPending, loadMyActive, currentAgentId])

  function applyClaimedRow(incident, loggedInAgentId, claimed) {
    const nextRow =
      claimed ??
      {
        ...incident,
        status: 'IN_PROGRESS',
        agent_id: loggedInAgentId,
      }

    setPendingIncidents(prev => prev.filter(i => i.id !== incident.id))
    setMyActiveIncidents(prev =>
      sortByUrgency([
        nextRow,
        ...prev.filter(i => i.id !== incident.id),
      ]),
    )
    setActivePanel('active')
    setAcceptingId(null)
  }

  async function handleAccept(incident) {
    const loggedInAgentId = getCurrentAgentId()
    if (!loggedInAgentId) {
      setError('Session expired — please sign in again.')
      return
    }

    setAcceptingId(incident.id)
    setError(null)

    // #region agent log
    fetch('http://127.0.0.1:7501/ingest/c12efe83-6414-4913-b137-e3a0c8e0b6e5', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Debug-Session-Id': '1a86c0',
      },
      body: JSON.stringify({
        sessionId: '1a86c0',
        hypothesisId: 'H1',
        location: 'AgentDashboard.jsx:handleAccept:api',
        message: 'claim_api_start',
        data: { incidentId: incident.id, agentId: loggedInAgentId },
        timestamp: Date.now(),
      }),
    }).catch(() => {})
    // #endregion

    try {
      const result = await claimIncident(incident.id)
      // #region agent log
      fetch('http://127.0.0.1:7501/ingest/c12efe83-6414-4913-b137-e3a0c8e0b6e5', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Debug-Session-Id': '1a86c0',
        },
        body: JSON.stringify({
          sessionId: '1a86c0',
          hypothesisId: 'H1',
          location: 'AgentDashboard.jsx:handleAccept:api',
          message: 'claim_api_ok',
          data: {
            incidentId: incident.id,
            status: result?.incident?.status ?? null,
          },
          timestamp: Date.now(),
        }),
      }).catch(() => {})
      // #endregion
      applyClaimedRow(incident, loggedInAgentId, result?.incident)
    } catch (apiErr) {
      const reason =
        apiErr instanceof ApiError && apiErr.detail?.reason
          ? apiErr.detail.reason
          : null
      // #region agent log
      fetch('http://127.0.0.1:7501/ingest/c12efe83-6414-4913-b137-e3a0c8e0b6e5', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Debug-Session-Id': '1a86c0',
        },
        body: JSON.stringify({
          sessionId: '1a86c0',
          hypothesisId: 'H1',
          location: 'AgentDashboard.jsx:handleAccept:api',
          message: 'claim_api_failed',
          data: {
            incidentId: incident.id,
            status: apiErr instanceof ApiError ? apiErr.status : null,
            reason,
            message: apiErr.message?.slice(0, 160) ?? null,
          },
          timestamp: Date.now(),
        }),
      }).catch(() => {})
      // #endregion
      if (reason === 'ALREADY_CLAIMED') {
        setPendingIncidents(prev => prev.filter(i => i.id !== incident.id))
        setError('This case is no longer in the unassigned queue.')
      } else {
        setError(apiErr.message)
      }
      setAcceptingId(null)
    }
  }

  async function handleResolve(incident) {
    const loggedInAgentId = getCurrentAgentId()
    if (!loggedInAgentId) {
      setError('Session expired — please sign in again.')
      return
    }

    setResolvingId(incident.id)
    setError(null)

    // #region agent log
    fetch('http://127.0.0.1:7501/ingest/c12efe83-6414-4913-b137-e3a0c8e0b6e5', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Debug-Session-Id': 'c791f6',
      },
      body: JSON.stringify({
        sessionId: 'c791f6',
        hypothesisId: 'H1-H4',
        location: 'AgentDashboard.jsx:handleResolve:pre_api',
        message: 'resolve_api_start',
        data: {
          incidentId: incident.id,
          hasAgentId: Boolean(loggedInAgentId),
          storedAgentId: loggedInAgentId,
          cardStatus: incident.status ?? null,
          cardAgentId: incident.agent_id ?? null,
          supabaseUrl: import.meta.env.VITE_SUPABASE_URL?.slice(-24) ?? null,
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {})
    // #endregion

    try {
      const result = await resolveIncident(incident.id)
      // #region agent log
      fetch('http://127.0.0.1:7501/ingest/c12efe83-6414-4913-b137-e3a0c8e0b6e5', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Debug-Session-Id': 'c791f6',
        },
        body: JSON.stringify({
          sessionId: 'c791f6',
          hypothesisId: 'H1',
          location: 'AgentDashboard.jsx:handleResolve:post_api',
          message: 'resolve_api_ok',
          data: {
            incidentId: incident.id,
            status: result?.incident?.status ?? null,
          },
          timestamp: Date.now(),
        }),
      }).catch(() => {})
      // #endregion
    } catch (apiErr) {
      const reason =
        apiErr instanceof ApiError && apiErr.detail?.reason
          ? apiErr.detail.reason
          : null
      // #region agent log
      fetch('http://127.0.0.1:7501/ingest/c12efe83-6414-4913-b137-e3a0c8e0b6e5', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Debug-Session-Id': 'c791f6',
        },
        body: JSON.stringify({
          sessionId: 'c791f6',
          hypothesisId: 'H1-H5',
          location: 'AgentDashboard.jsx:handleResolve:post_api',
          message: 'resolve_api_error',
          data: {
            incidentId: incident.id,
            status: apiErr instanceof ApiError ? apiErr.status : null,
            reason,
            errorMessage: apiErr.message?.slice(0, 200) ?? null,
          },
          timestamp: Date.now(),
        }),
      }).catch(() => {})
      // #endregion
      setError(apiErr.message)
      setResolvingId(null)
      return
    }

    setResolvingId(null)
    setResolveFlashIds(prev => new Set(prev).add(incident.id))

    window.setTimeout(() => {
      setResolveFlashIds(prev => {
        const next = new Set(prev)
        next.delete(incident.id)
        return next
      })
      setExitingIds(prev => new Set(prev).add(incident.id))

      window.setTimeout(() => {
        setMyActiveIncidents(prev => prev.filter(i => i.id !== incident.id))
        setExitingIds(prev => {
          const next = new Set(prev)
          next.delete(incident.id)
          return next
        })
      }, RESOLVE_EXIT_MS)
    }, RESOLVE_SUCCESS_MS)
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
            <p className="header-pending-count">{pendingIncidents.length}</p>
          </div>

          <div className="header-actions">
            <div className={syncPillClass(liveStatus)}>
              <Radio className="sync-pill-icon" aria-hidden />
              <span className="sync-pill-text">{syncPillLabel(liveStatus)}</span>
            </div>

            <AvatarMenu
              agentName={agentName}
              initials={initials}
              onSignOut={onSignOut}
            />
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
          <StatsOverviewBar incidents={pendingIncidents} />
        </section>

        <div className="dashboard-panels" role="tablist" aria-label="Incident queues">
          <button
            type="button"
            role="tab"
            aria-selected={activePanel === 'queue'}
            className={`panel-tab${activePanel === 'queue' ? ' panel-tab--active' : ''}`}
            onClick={() => setActivePanel('queue')}
          >
            Unassigned Emergency Queue
            <span className="panel-tab-count">{pendingIncidents.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activePanel === 'active'}
            className={`panel-tab${activePanel === 'active' ? ' panel-tab--active' : ''}`}
            onClick={() => setActivePanel('active')}
          >
            My Active Rescue Operations
            <span className="panel-tab-count">{myActiveIncidents.length}</span>
          </button>
        </div>

        {loading ? (
          <div className="state-panel">
            <Loader2 className="state-panel-spinner" aria-hidden />
            <p className="state-panel-title">Loading incidents…</p>
          </div>
        ) : (
          <>
            <section
              className="dashboard-panel"
              role="tabpanel"
              hidden={activePanel !== 'queue'}
            >
              <h2 className="panel-heading">Unassigned Emergency Queue</h2>
              {pendingIncidents.length === 0 ? (
                <div className="state-panel state-panel--empty state-panel--nested">
                  <Activity className="state-panel-icon" aria-hidden />
                  <p className="state-panel-title">No pending cases</p>
                  <p className="state-panel-desc">
                    New incidents from Telegram will appear here automatically.
                  </p>
                </div>
              ) : (
                <div className="incident-grid">
                  {pendingIncidents.map((incident, index) => (
                    <IncidentCard
                      key={incident.id}
                      incident={incident}
                      variant="queue"
                      onAccept={handleAccept}
                      accepting={acceptingId === incident.id}
                      staggerIndex={index}
                    />
                  ))}
                </div>
              )}
            </section>

            <section
              className="dashboard-panel"
              role="tabpanel"
              hidden={activePanel !== 'active'}
            >
              <h2 className="panel-heading">My Active Rescue Operations</h2>
              {myActiveIncidents.length === 0 ? (
                <div className="state-panel state-panel--empty state-panel--nested">
                  <Activity className="state-panel-icon" aria-hidden />
                  <p className="state-panel-title">No active cases</p>
                  <p className="state-panel-desc">
                    Accept a case from the emergency queue to begin a rescue operation.
                  </p>
                </div>
              ) : (
                <div className="incident-grid">
                  {myActiveIncidents.map((incident, index) => (
                    <IncidentCard
                      key={incident.id}
                      incident={incident}
                      variant="active"
                      onResolve={handleResolve}
                      resolving={resolvingId === incident.id}
                      resolveSuccess={resolveFlashIds.has(incident.id)}
                      exiting={exitingIds.has(incident.id)}
                      staggerIndex={index}
                    />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}
