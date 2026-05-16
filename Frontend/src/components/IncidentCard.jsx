import { useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const PRIORITY_ICONS = { critical: '●', high: '●', medium: '●', low: '●' }
const SENTIMENT_ICONS = { positive: '↑', neutral: '→', negative: '↓' }

const STATUS_NEXT = { open: 'assigned', assigned: 'resolved', resolved: 'open' }
const STATUS_LABEL = { open: 'Mark Assigned', assigned: 'Mark Resolved', resolved: 'Re-open' }

function ScoreBar({ label, value = 0, type }) {
  const pct = Math.round((value ?? 0) * 100)
  return (
    <div className="score-row">
      <span className="score-key">{label}</span>
      <div className="score-track">
        <div className={`score-fill ${type}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="score-pct">{pct}%</span>
    </div>
  )
}

function Section({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="expand-section">
      <button className="expand-btn" onClick={() => setOpen(o => !o)}>
        <span>{title}</span>
        <span className={`chevron ${open ? 'open' : ''}`}>▼</span>
      </button>
      {open && <div className="expand-body">{children}</div>}
    </div>
  )
}

function parseActions(text) {
  if (!text) return []
  return text.split(/\n|(?=\d+\.\s)/).map(s => s.replace(/^\d+\.\s*/, '').trim()).filter(Boolean)
}

function timeAgo(str) {
  const s = (Date.now() - new Date(str)) / 1000
  if (s < 60)   return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return new Date(str).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

function isNew(str) { return (Date.now() - new Date(str)) / 1000 < 20 }

export default function IncidentCard({ incident }) {
  const {
    id, priority = 'low',
    caller_name, location, created_at,
    urgency = 0, stress = 0, frustration = 0,
    sentiment, transcript, action_items,
    incident_type, status: initialStatus = 'open',
  } = incident

  const [status,   setStatus]   = useState(initialStatus)
  const [updating, setUpdating] = useState(false)

  async function updateStatus(newStatus) {
    setUpdating(true)
    try {
      await fetch(`${API_URL}/incident/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      })
      setStatus(newStatus)
    } catch (e) {
      console.error('Status update failed:', e)
    }
    setUpdating(false)
  }

  const actions = parseActions(action_items)

  return (
    <div className={`card ${priority}`}>
      <div className="card-stripe" />
      <div className="card-inner">

        {/* Header */}
        <div className="card-head">
          <div>
            <div className="card-caller-name">
              {caller_name || 'Unknown Caller'}
              {isNew(created_at) && <span className="new-tag">NEW</span>}
            </div>
            <div className="card-meta">
              <span>📍 {location || 'Unknown'}</span>
              <span>·</span>
              <span>{timeAgo(created_at)}</span>
            </div>
          </div>

          <div className="card-badges">
            {incident_type && (
              <div className={`type-badge ${incident_type}`}>
                {incident_type === 'disaster' ? '🌊 Disaster' : '🏥 Medical'}
              </div>
            )}
            <div className={`p-badge ${priority}`}>
              <span style={{ fontSize: 7 }}>{PRIORITY_ICONS[priority]}</span>
              {priority}
            </div>
          </div>
        </div>

        {/* Sentiment */}
        {sentiment && (
          <div className={`sentiment ${sentiment}`}>
            {SENTIMENT_ICONS[sentiment]} {sentiment}
          </div>
        )}

        {/* Scores */}
        <div className="scores">
          <ScoreBar label="Urgency"     value={urgency}     type="urgency"     />
          <ScoreBar label="Stress"      value={stress}      type="stress"      />
          <ScoreBar label="Frustration" value={frustration} type="frustration" />
        </div>

        {/* Action items */}
        {actions.length > 0 && (
          <Section title="Action Items" defaultOpen>
            <ul className="action-list">
              {actions.map((a, i) => (
                <li key={i} className="action-item">
                  <span className="action-arrow">→</span>{a}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {/* Transcript */}
        {transcript && (
          <Section title="Transcript">
            <p>{transcript}</p>
          </Section>
        )}

        {/* Status update */}
        <div className="status-update-row">
          <span className="status-update-label">Status:</span>
          <span className={`status-badge ${status}`}>{status}</span>
          <div style={{ flex: 1 }} />
          <button
            className="status-btn"
            onClick={() => updateStatus(STATUS_NEXT[status])}
            disabled={updating}
          >
            {updating ? '...' : STATUS_LABEL[status]}
          </button>
        </div>

      </div>
    </div>
  )
}