import { useState, useEffect } from 'react'
import Dashboard     from './components/Dashboard'
import AudioRecorder from './components/AudioRecorder'
import StatsBar      from './components/StatsBar'
import { supabase, fetchIncidents, subscribeToIncidents } from './lib/supabase'
import './index.css'
import './App.css'

function Clock() {
  const [t, setT] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setT(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="header-clock">
      {t.toLocaleDateString('en-GB', { day:'2-digit', month:'short' })}
      &nbsp;·&nbsp;
      {t.toLocaleTimeString('en-GB', { hour12: false })}
    </div>
  )
}

export default function App() {
  const [incidents,   setIncidents]   = useState([])
  const [liveStatus,  setLiveStatus]  = useState('connecting')

  useEffect(() => {
    fetchIncidents().then(data => setIncidents(data))

    const ch = subscribeToIncidents(row =>
      setIncidents(prev => [row, ...prev])
    )

    ch.subscribe(s => setLiveStatus(s === 'SUBSCRIBED' ? 'live' : 'connecting'))
    return () => supabase.removeChannel(ch)
  }, [])

  return (
    <div className="app">

      {/* Header */}
      <header className="header">
        <div className="header-brand">
          <div className="brand-mark">
            <div className="brand-icon">
              {/* Signal / waveform icon */}
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M1 7 Q2.5 3 4 7 Q5.5 11 7 7 Q8.5 3 10 7 Q11.5 11 13 7"
                      stroke="#A8FF3E" strokeWidth="1.5"
                      strokeLinecap="round" strokeLinejoin="round" fill="none"/>
              </svg>
            </div>
            <span className="brand-name">RESQNET</span>
          </div>
          <div className="brand-sep" />
          <span className="brand-sub">Disaster Call Management</span>
        </div>

        <div className="header-right">
          <div className={`signal-status ${liveStatus}`}>
            <span className="signal-dot" />
            {liveStatus === 'live' ? 'Signal Active' : 'Connecting...'}
          </div>
          <Clock />
        </div>
      </header>

      {/* Telemetry bar */}
      <StatsBar incidents={incidents} />

      {/* Main */}
      <div className="app-body">
        <aside className="left-panel">
          <AudioRecorder />
        </aside>
        <main className="right-panel">
          <Dashboard incidents={incidents} />
        </main>
      </div>

    </div>
  )
}