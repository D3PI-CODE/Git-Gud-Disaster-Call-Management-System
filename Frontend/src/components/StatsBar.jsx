export default function StatsBar({ incidents }) {
  const c = incidents.reduce(
    (a, i) => {
      a.total++
      if (i.priority) a[i.priority] = (a[i.priority] ?? 0) + 1
      return a
    },
    { total: 0, critical: 0, high: 0, medium: 0, low: 0 }
  )

  const fmt = n => String(n).padStart(2, '0')

  return (
    <div className="telemetry">
      <div className="telem-block t-total">
        <span className="telem-label">Total</span>
        <span className="telem-value">{fmt(c.total)}</span>
      </div>
      <div className="telem-block t-critical">
        <span className="telem-label">Critical</span>
        <span className="telem-value">{fmt(c.critical)}</span>
      </div>
      <div className="telem-block t-high">
        <span className="telem-label">High</span>
        <span className="telem-value">{fmt(c.high)}</span>
      </div>
      <div className="telem-block t-medium">
        <span className="telem-label">Medium</span>
        <span className="telem-value">{fmt(c.medium)}</span>
      </div>
      <div className="telem-block t-low">
        <span className="telem-label">Low</span>
        <span className="telem-value">{fmt(c.low)}</span>
      </div>
    </div>
  )
}