import { useState } from 'react'
import IncidentCard from './IncidentCard'

const PRIORITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 }

const FILTERS = [
  { key: 'all',      label: 'All' },
  { key: 'critical', label: 'Critical' },
  { key: 'high',     label: 'High' },
  { key: 'disaster', label: 'Disaster' },
  { key: 'medical',  label: 'Medical' },
  { key: 'open',     label: 'Open' },
  { key: 'resolved', label: 'Resolved' },
]

export default function Dashboard({ incidents }) {
  const [activeFilter, setActiveFilter] = useState('all')

  const filtered = incidents.filter(i => {
    if (activeFilter === 'all')      return true
    if (activeFilter === 'critical') return i.priority === 'critical'
    if (activeFilter === 'high')     return i.priority === 'high'
    if (activeFilter === 'disaster') return i.incident_type === 'disaster'
    if (activeFilter === 'medical')  return i.incident_type === 'medical'
    if (activeFilter === 'open')     return i.status === 'open'
    if (activeFilter === 'resolved') return i.status === 'resolved'
    return true
  })

  const sorted = [...filtered].sort(
    (a, b) => (PRIORITY_ORDER[a.priority] ?? 4) - (PRIORITY_ORDER[b.priority] ?? 4)
  )

  return (
    <div>
      {/* Header */}
      <div className="feed-header">
        <div className="section-label" style={{ marginBottom: 0, flex: 1 }}>
          <span className="sl-text">Live Incident Feed</span>
          <span className="sl-line" />
        </div>
        <span className="feed-count" style={{ marginLeft: 14 }}>
          {sorted.length} / {incidents.length}
        </span>
      </div>

      {/* Filter tabs */}
      <div className="filter-tabs">
        {FILTERS.map(f => (
          <button
            key={f.key}
            className={`filter-tab ${activeFilter === f.key ? 'active' : ''}`}
            onClick={() => setActiveFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Cards */}
      {sorted.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📡</div>
          <div className="empty-title">No incidents found</div>
          <div className="empty-sub">
            {activeFilter === 'all'
              ? 'Incidents from the Telegram bot will appear here in real time.'
              : `No ${activeFilter} incidents. Try a different filter.`}
          </div>
        </div>
      ) : (
        <div className="incident-list">
          {sorted.map(inc => (
            <IncidentCard key={inc.id} incident={inc} />
          ))}
        </div>
      )}
    </div>
  )
}