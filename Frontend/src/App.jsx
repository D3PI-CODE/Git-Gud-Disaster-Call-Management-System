import { useState, useEffect } from 'react'
import Dashboard    from './components/Dashboard'
import AudioRecorder from './components/AudioRecorder'
import StatsBar     from './components/StatsBar'
import { supabase, fetchIncidents, subscribeToIncidents } from './lib/supabase'
import './index.css'
import './App.css'

function Clock() {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="clock">
      {time.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
      {' · '}
      {time.toLocaleTimeString('en-GB', { hour12: false })}
    </div>
  )
}

export default function App() {
  const [incidents, setIncidents] = useState([])
  const [liveStatus, setLiveStatus] = useState('connecting')

  useEffect(() => {
    // Load existing incidents on mount
    fetchIncidents().then(data => setIncidents(data))

    // Subscribe to new incidents in real time
    const channel = subscribeToIncidents(newIncident => {
      setIncidents(prev => [newIncident, ...prev])
    })

    channel.subscribe(status => {
      setLiveStatus(status === 'SUBSCRIBED' ? 'live' : 'connecting')
    })

    return () => supabase.removeChannel(channel)
  }, [])

  return (
    <div className="app">

      {/* ─── Header ──────────────────────────────────────── */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo">
            <span className="logo-icon">⚡</span>
            <span className="logo-text">RESQNET</span>
          </div>
          <span className="header-sub">Disaster Call Management</span>
        </div>

        <div className="header-right">
          <div className={`live-indicator ${liveStatus}`}>
            <span className="live-dot" />
            {liveStatus === 'live' ? 'LIVE' : 'CONNECTING'}
          </div>
          <Clock />
        </div>
      </header>

      {/* ─── Stats Bar ───────────────────────────────────── */}
      <StatsBar incidents={incidents} />

      {/* ─── Main ────────────────────────────────────────── */}
      <main className="app-main">
        <aside className="recorder-panel">
          <AudioRecorder />
        </aside>

        <section className="dashboard-panel">
          <Dashboard incidents={incidents} />
        </section>
      </main>

    </div>
  )
}