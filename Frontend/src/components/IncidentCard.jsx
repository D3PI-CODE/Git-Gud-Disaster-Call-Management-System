import { useState } from 'react'

const PRIORITY_ICONS = { MEDICAL: '✚', DISASTER: '⚠', critical: '●', high: '●', medium: '●', low: '●' }

const SENTIMENT_ICONS = { positive: '↑', neutral: '→', negative: '↓' }

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
  return text
    .split(/\n|(?=\d+\.\s)/)
    .map(s => s.replace(/^\d+\.\s*/, '').trim())
    .filter(Boolean)
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
    incident_type = 'DISASTER',
    users,
    created_at,
    urgency_score = 0,
    transcript,
    structured_data = {},
  } = incident

  const {
    location = 'Unknown',
    stress = 0,
    frustration = 0,
    sentiment,
    action_items = '',
  } = structured_data || {}

  const caller_name = users?.name || 'Unknown Caller'
  const display_priority = incident_type === 'MEDICAL' ? 'critical' : 'high'

  const actions = parseActions(action_items)

  return (
    <div className={`card ${display_priority}`}>
      <div className="card-top" />
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

          <div className={`p-badge ${display_priority}`}>
            <span style={{ fontSize: 7 }}>{PRIORITY_ICONS[incident_type] || PRIORITY_ICONS[display_priority]}</span>
            {incident_type}
          </div>
        </div>

        {/* Sentiment */}
        {sentiment && (
          <div className={`sentiment ${sentiment}`}>
            {SENTIMENT_ICONS[sentiment]} {sentiment}
          </div>
        )}

        {/* Score bars */}
        <div className="scores">
          <ScoreBar label="Urgency"     value={urgency_score} type="urgency"     />
          <ScoreBar label="Stress"      value={stress}      type="stress"      />
          <ScoreBar label="Frustration" value={frustration} type="frustration" />
        </div>

        {/* Action items */}
        {actions.length > 0 && (
          <Section title="Action Items" defaultOpen>
            <ul className="action-list">
              {actions.map((a, i) => (
                <li key={i} className="action-item">
                  <span className="action-arrow">→</span>
                  {a}
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

      </div>
    </div>
  )
}