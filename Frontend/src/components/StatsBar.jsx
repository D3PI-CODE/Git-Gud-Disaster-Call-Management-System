export default function StatsBar({ incidents }) {
  const counts = incidents.reduce(
    (acc, i) => {
      acc.total++
      if (i.priority) acc[i.priority] = (acc[i.priority] ?? 0) + 1
      return acc
    },
    { total: 0, critical: 0, high: 0, medium: 0, low: 0 }
  )

  return (
    <div className="stats-bar">
      <span className="stats-label">Incidents</span>

      <div className="stat-chip total">
        <span>ALL</span>
        <span>{counts.total}</span>
      </div>

      <div className="stat-chip critical">
        <span>⬆ CRITICAL</span>
        <span>{counts.critical}</span>
      </div>

      <div className="stat-chip high">
        <span>HIGH</span>
        <span>{counts.high}</span>
      </div>

      <div className="stat-chip medium">
        <span>MEDIUM</span>
        <span>{counts.medium}</span>
      </div>

      <div className="stat-chip low">
        <span>LOW</span>
        <span>{counts.low}</span>
      </div>
    </div>
  )
}