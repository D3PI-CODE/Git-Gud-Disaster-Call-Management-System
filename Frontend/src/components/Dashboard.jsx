import IncidentCard from './IncidentCard'

const PRIORITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 }

export default function Dashboard({ incidents }) {
  const sorted = [...incidents].sort(
    (a, b) => (PRIORITY_ORDER[a.priority] ?? 4) - (PRIORITY_ORDER[b.priority] ?? 4)
  )

  return (
    <div>
      <div className="feed-header">
        <div className="section-label" style={{ marginBottom: 0, flex: 1 }}>
          <span className="section-label-text">Live Incident Feed</span>
          <span className="section-label-line" />
        </div>
        <span className="feed-count" style={{ marginLeft: 14 }}>
          {sorted.length} incident{sorted.length !== 1 ? 's' : ''}
        </span>
      </div>

      {sorted.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📡</div>
          <div className="empty-title">Awaiting incoming calls</div>
          <div className="empty-sub">
            Submit a call recording using the panel on the left.
            It will appear here instantly via live sync.
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