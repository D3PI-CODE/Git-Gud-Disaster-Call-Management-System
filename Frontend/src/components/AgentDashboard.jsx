import { useState, useEffect, useCallback, useRef } from 'react'
import {
  MapPin,
  Loader2,
  User,
  Phone,
  Activity,
  ShieldAlert,
  Flame,
  Clock,
  Radio,
  LogOut,
  ChevronDown,
} from 'lucide-react'
import { supabase, attachAgentToken } from '../lib/supabaseClient'
import {
  getAuthToken,
  getCurrentAgentId,
  getStoredUser,
  claimIncident,
  ApiError,
} from '../lib/api'
import './AgentDashboard.css'

const AGENT_LOCATION_KEY = 'resqnet_agent_location'

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

// Maps label strings → approximate 0-1 urgency score
const PRIORITY_URGENCY = { critical: 0.92, high: 0.70, medium: 0.45, low: 0.18 }
const STRESS_LEVEL_URGENCY = { critical: 0.92, high: 0.72, moderate: 0.50, low: 0.20 }
const TONE_URGENCY = {
  panicked: 0.95, frantic: 0.93, screaming: 0.90, fearful: 0.86,
  distressed: 0.78, urgent: 0.74, anxious: 0.68, upset: 0.64,
  worried: 0.55, concerned: 0.50, frustrated: 0.52, confused: 0.42,
  neutral: 0.25, calm: 0.18, polite: 0.15,
}

/**
 * Derive the best available urgency score (0–1) from all signals in the
 * incident row.  Falls through from most-authoritative to least:
 *   1. urgency_score DB column (set by the full pipeline)
 *   2. structured_data.urgency  (stored since the latest backend fix)
 *   3. Raw VALSEA stress/urgency in the nested valsea object
 *   4. structured_data stress/frustration numeric fields
 *   5. priority label  →  mapped score
 *   6. stress_level label  →  mapped score
 *   7. tone label  →  mapped score
 *   8. sentiment  →  mapped score
 */
function deriveUrgency(incident) {
  // 1. Top-level urgency_score
  const direct = Number(incident.urgency_score)
  if (direct > 0 && direct <= 1) return direct
  if (direct > 1) return direct / 100   // guard: someone stored as 0-100

  const sd = parseStructured(incident.structured_data)

  // 2. Explicit urgency saved in structured_data (new pipeline records)
  const sdUrgency = Number(sd.urgency)
  if (sdUrgency > 0) return sdUrgency > 1 ? sdUrgency / 10 : sdUrgency

  // 3. VALSEA sub-dict (auto-detect 0-10 vs 0-1 scale)
  const v = sd.valsea || {}
  const rawVU = Number(v.urgency || 0)
  const rawVS = Number(v.stress || 0)
  const scale = (rawVU > 1 || rawVS > 1) ? 10 : 1
  const valseaScore = Math.max(rawVU / scale, rawVS / scale * 0.9)
  if (valseaScore > 0.05) return Math.min(valseaScore, 0.98)

  // 4. Normalised stress + frustration stored at structured_data root
  const stress = Number(sd.stress || 0)
  const frustration = Number(sd.frustration || 0)
  const stressNorm = stress > 1 ? stress / 10 : stress
  const frustNorm = frustration > 1 ? frustration / 10 : frustration
  const metricScore = Math.max(stressNorm, frustNorm * 0.8)
  if (metricScore > 0.05) return Math.min(metricScore, 0.98)

  // 5. priority label
  const priority = String(sd.priority || incident.priority || '').toLowerCase()
  if (PRIORITY_URGENCY[priority]) return PRIORITY_URGENCY[priority]

  // 6. stress_level label
  const sl = String(sd.stress_level || '').toLowerCase()
  if (STRESS_LEVEL_URGENCY[sl]) return STRESS_LEVEL_URGENCY[sl]

  // 7. tone label (fuzzy match)
  const tone = String(sd.tone || '').toLowerCase()
  for (const [keyword, score] of Object.entries(TONE_URGENCY)) {
    if (tone.includes(keyword)) return score
  }

  // 8. sentiment
  if (sd.sentiment === 'negative') return 0.38
  if (sd.sentiment === 'positive') return 0.12

  return 0.20  // unknown — show a non-zero baseline
}

function urgencyTier(score) {
  const n = normalizeScore(score)
  if (n > 80) return 'critical'
  if (n >= 50) return 'high'
  if (n >= 30) return 'medium'
  return 'low'
}

function sortByUrgency(list) {
  return [...list].sort((a, b) => deriveUrgency(b) - deriveUrgency(a))
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
    i => urgencyTier(deriveUrgency(i)) === 'critical',
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

// Fields handled by dedicated card sections or not fit for tag display
const STRUCTURED_TAG_SKIP = new Set([
  'location', 'action_items', 'valsea', 'summary', 'content',
  'main_points', 'priority', 'tone', 'urgency', 'source',
  'caller_name', 'transcript',
])

// Only show these specific keys as metadata tags (allowlist approach)
const STRUCTURED_TAG_ALLOW = new Set([
  'stress_level', 'sentiment', 'language', 'stress', 'frustration',
  'caller_name', 'incident_type',
])

// Tags that are numeric (0–1 scale) → displayed as a percentage
const NUMERIC_TAG_KEYS = new Set(['stress', 'frustration'])

function StructuredTags({ data, incidentType }) {
  const entries = Object.entries(data).filter(([k, v]) => {
    if (!STRUCTURED_TAG_ALLOW.has(k)) return false
    if (v == null || String(v).trim() === '' || String(v) === '0') return false
    // Skip near-zero numerics (not meaningful to display)
    if (typeof v === 'number' && v < 0.05) return false
    // incident_type comes from the incident row, skip if passed separately
    if (k === 'incident_type') return false
    return true
  })

  // Add incident_type from the prop if available
  const extra = incidentType ? [['type', incidentType]] : []
  const allEntries = [...extra, ...entries]

  if (allEntries.length === 0) return null

  return (
    <div className="tag-container">
      {allEntries.map(([key, val]) => {
        const display = NUMERIC_TAG_KEYS.has(key)
          ? `${Math.round(Number(val) * 100)}%`
          : String(val)
        return (
          <span key={key} className={`tag-pill tag-pill--${key.replace(/_/g, '-')}`}>
            <span className="tag-pill-key">{key.replace(/_/g, ' ')}</span>
            <span className="tag-pill-sep">·</span>
            <span>{display}</span>
          </span>
        )
      })}
    </div>
  )
}

/**
 * Return a short description for the card headline.
 * - New records: structured_data.content is a distinct 1-sentence summary.
 * - Old records: content === summary (backend set them equal); extract only
 *   the first sentence so they don't look identical on the card.
 */
function deriveContent(structured) {
  const content = String(structured.content || '').trim()
  const summary = String(structured.summary || '').trim()

  if (!content) return summary.split(/\.\s+/)[0] || ''

  // If backend stored content = summary (pre-fix data), extract first sentence
  if (content === summary) {
    const first = content.split(/\.\s+/)[0]
    return first.endsWith('.') ? first : first + (first ? '.' : '')
  }

  return content
}

/**
 * Strip the portion of `summary` that duplicates `content`.
 *
 * Two strategies:
 *  1. Exact prefix: summary starts with the content text (case-insensitive).
 *  2. Word-overlap: the first sentence of summary shares ≥60% of significant
 *     words with content — common for old records where the LLM reused the
 *     same opening phrase.
 *
 * Returns the remainder after the overlapping prefix is removed, or the
 * original summary if no meaningful overlap is found.
 */
function trimRedundantPrefix(content, summary) {
  if (!summary || !content) return summary

  const c = content.trim()
  const s = summary.trim()

  // 1. Exact prefix match (case-insensitive)
  if (s.toLowerCase().startsWith(c.toLowerCase())) {
    return s.slice(c.length).replace(/^[\s.,]+/, '').trim()
  }

  // 2. Word-overlap on the first sentence of summary
  const sentences = s.split(/(?<=[.!?])\s+/)
  if (sentences.length < 2) return summary   // only one sentence — nothing to trim

  const significant = (str) =>
    str.toLowerCase().split(/\W+/).filter(w => w.length > 3)

  const cWords = significant(c)
  const firstWords = significant(sentences[0])

  if (cWords.length >= 3 && firstWords.length >= 3) {
    const overlap = cWords.filter(w => firstWords.includes(w)).length
    const sim = overlap / Math.max(cWords.length, firstWords.length)
    if (sim >= 0.60) {
      return sentences.slice(1).join(' ').trim()
    }
  }

  return summary
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

function IncidentCard({ incident, onAccept, accepting, staggerIndex, claimed }) {
  const structured = parseStructured(incident.structured_data)
  const location = structured.location || 'Location unknown'
  const urgency = deriveUrgency(incident)
  const score = normalizeScore(urgency)
  const tier = urgencyTier(urgency)
  const isMedical = incident.incident_type === 'MEDICAL'
  const typeLabel = incident.incident_type || 'DISASTER'
  const tone = structured.tone || ''
  const priority = structured.priority || incident.priority || ''

  const callerName = incident.users?.name || structured.caller_name || ''
  const contactNumber = incident.users?.contact_number || ''

  // Short headline (content) — distinct from the full dispatcher summary
  const content = deriveContent(structured)
  // Full dispatcher summary — strip any prefix that repeats the headline
  const rawSummary = String(structured.summary || '').trim()
  const displaySummary = trimRedundantPrefix(content, rawSummary)
  const showSummary = displaySummary && displaySummary !== content && displaySummary.length > 20

  return (
    <article
      className={`incident-card incident-card--${tier}`}
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
        {(tone || priority) && (
          <div className="incident-card-meta-row">
            {tone && <span className="meta-pill meta-pill--tone">{tone}</span>}
            {priority && (
              <span className={`meta-pill meta-pill--priority meta-pill--${priority.toLowerCase()}`}>
                {priority}
              </span>
            )}
          </div>
        )}
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

        {(callerName || contactNumber) && (
          <div className="caller-info-row">
            {callerName && (
              <div className="caller-row">
                <User className="caller-icon" aria-hidden />
                <span className="caller-text">{callerName}</span>
              </div>
            )}
            {contactNumber && (
              <div className="caller-row">
                <Phone className="caller-icon" aria-hidden />
                <span className="caller-text">{contactNumber}</span>
              </div>
            )}
          </div>
        )}

        {/* Short headline — what happened, in one sentence */}
        {content && <p className="incident-content">{content}</p>}

        {/* Full dispatcher summary — only when it adds information beyond the headline */}
        {showSummary && (
          <p className="incident-summary">{displaySummary}</p>
        )}

        <StructuredTags data={structured} incidentType={incident.incident_type} />
      </div>

      <footer className="incident-card-footer">
        {claimed ? (
          <button type="button" className="btn-claimed" disabled>
            Case Claimed
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
                      claimed
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
