export default function StatsBar({ incidents }) {
  const c = incidents.reduce(
    (a, i) => { a.total++; if (i.priority) a[i.priority] = (a[i.priority] ?? 0) + 1; return a },
    { total: 0, critical: 0, high: 0, medium: 0, low: 0 }
  )
  const fmt = n => String(n).padStart(2, '0')
  return (
    <div className="telemetry">
      {[
        { cls: 't-total',    label: 'Total',    val: c.total    },
        { cls: 't-critical', label: 'Critical', val: c.critical },
        { cls: 't-high',     label: 'High',     val: c.high     },
        { cls: 't-medium',   label: 'Medium',   val: c.medium   },
        { cls: 't-low',      label: 'Low',      val: c.low      },
      ].map(({ cls, label, val }) => (
        <div key={cls} className={`telem-block ${cls}`}>
          <span className="telem-label">{label}</span>
          <span className="telem-value">{fmt(val)}</span>
        </div>
      ))}
    </div>
  )
}