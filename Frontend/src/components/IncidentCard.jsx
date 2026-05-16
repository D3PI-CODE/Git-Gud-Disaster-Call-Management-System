import { useState } from 'react'

const PRIORITY_ICONS = {
  critical: '🔴',
  high:     '🟠',
  medium:   '🟡',
  low:      '🟢',
}

const SENTIMENT_ICONS = {
  positive: '↑',
  neutral:  '→',
  negative: '↓',
}

function ScoreBar({ label, value = 0, type }) {
  const pct = Math.round((value ?? 0) * 100)
  return (
    <div className="score-row">
      <span className="score-label">{label}</span>
      <div className="score-track">
        <div
          className={`score-fill ${type}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="score-value">{pct}%</span>
    </div>
  )
}

function CollapsibleSection({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="card-section">
      <button className="section-toggle" onClick={() => setOpen(o => !o)}>
        <span>{title}</span>
        <span className={`section-chevron ${open ? 'open' : ''}`}>▼</span>
      </button>
      {open && <div className="section-content">{children}</div>}
    </div>
  )
}

function parseActionItems(text) {
  if (!text) return []
  // Split on newlines or numbered list patterns
  return text
    .split(/\n|(?=\d+\.\s)/)
    .map(s => s.replace(/^\d+\.\s*/, '').trim())
    .filter(Boolean)
}

function parseValidDate(dateStr) {
  const date = new Date(dateStr)
  return Number.isNaN(date.getTime()) ? null : date
}

function timeAgo(dateStr) {
  const date = parseValidDate(dateStr)
  if (!date) return 'Unknown time'

  const diff = (Date.now() - date.getTime()) / 1000
  if (diff < 60)  return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function isNew(dateStr) {
  const date = parseValidDate(dateStr)
  if (!date) return false
  return (Date.now() - date.getTime()) / 1000 < 20
}

export default function IncidentCard({ incident }) {
  const {
    priority = 'low',
    caller_name,
    location,
    created_at,
    urgency      = 0,
    stress       = 0,
    frustration  = 0,
    sentiment,
    transcript,
    action_items,
  } = incident

  const actionList = parseActionItems(action_items)

  return (
    <div className={`incident-card priority-${priority}`}>
      <div className="card-stripe" />

      <div className="card-body">
        {/* Header */}
        <div className="card-header">
          <div className="card-caller">
            <div className="caller-name">
              {caller_name || 'Unknown Caller'}
              {isNew(created_at) && (
                <span className="new-badge" style={{ marginLeft: 8 }}>NEW</span>
              )}
            </div>
            <div className="caller-meta">
              <span>📍 {location || 'Unknown location'}</span>
              <span>🕐 {timeAgo(created_at)}</span>
            </div>
          </div>

          <div className={`priority-badge ${priority}`}>
            {PRIORITY_ICONS[priority]} {priority}
          </div>
        </div>

        {/* Sentiment */}
        {sentiment && (
          <div className={`sentiment-chip ${sentiment}`}>
            {SENTIMENT_ICONS[sentiment]} {sentiment}
          </div>
        )}

        {/* Score Bars */}
        <div className="score-bars">
          <ScoreBar label="Urgency"     value={urgency}     type="urgency"     />
          <ScoreBar label="Stress"      value={stress}      type="stress"      />
          <ScoreBar label="Frustration" value={frustration} type="frustration" />
        </div>

        {/* Collapsible: Action Items */}
        {actionList.length > 0 && (
          <CollapsibleSection title="Action Items" defaultOpen>
            <ul className="action-list">
              {actionList.map((item, i) => (
                <li key={i} className="action-item">{item}</li>
              ))}
            </ul>
          </CollapsibleSection>
        )}

        {/* Collapsible: Transcript */}
        {transcript && (
          <CollapsibleSection title="Transcript">
            <p>{transcript}</p>
          </CollapsibleSection>
        )}
      </div>
    </div>
  )
}