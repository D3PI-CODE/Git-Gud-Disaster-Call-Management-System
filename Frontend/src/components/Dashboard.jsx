import IncidentCard from './IncidentCard'

const PRIORITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 }

export default function Dashboard({ incidents }) {
  const sorted = [...incidents].sort(
    (a, b) =>
      (PRIORITY_ORDER[a.priority] ?? 4) - (PRIORITY_ORDER[b.priority] ?? 4)
  )

  return (
    <div>
      <div className="dashboard-header">
        <span className="panel-title" style={{ marginBottom: 0 }}>
          Incident Feed
        </span>
        <span className="incident-count">
          {sorted.length} incident{sorted.length !== 1 ? 's' : ''}
        </span>
      </div>

      {sorted.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📡</div>
          <div className="empty-title">No incidents yet</div>
          <div className="empty-sub">
            Submit a call recording to see it appear here in real time
          </div>
        </div>
      ) : (
        <div className="incident-list">
          {sorted.map(incident => (
            <IncidentCard key={incident.id} incident={incident} />
          ))}
        </div>
      )}
    </div>
  )
}