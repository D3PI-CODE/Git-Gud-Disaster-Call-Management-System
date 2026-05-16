import { useState, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Dashboard      from './components/Dashboard'
import AudioRecorder  from './components/AudioRecorder'
import StatsBar       from './components/StatsBar'
import Login          from './components/Login'
import ProtectedRoute from './components/ProtectedRoute'
import { supabase, fetchIncidents, subscribeToIncidents } from './lib/supabase'
import './index.css'
import './App.css'

/* ── Theme toggle button ────────────────────────────────── */
export function ThemeToggle({ theme, onToggle }) {
  return (
    <button
      className="theme-toggle"
      onClick={onToggle}
      title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
    >
      {theme === 'dark' ? (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="5" />
          <line x1="12" y1="1"     x2="12" y2="3" />
          <line x1="12" y1="21"    x2="12" y2="23" />
          <line x1="4.22"  y1="4.22"  x2="5.64"  y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1"  y1="12" x2="3"  y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22"  y1="19.78" x2="5.64"  y2="18.36" />
          <line x1="18.36" y1="5.64"  x2="19.78" y2="4.22" />
        </svg>
      ) : (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  )
}

/* ── Clock ──────────────────────────────────────────────── */
function Clock() {
  const [t, setT] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setT(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="header-clock">
      {t.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}
      &nbsp;·&nbsp;
      {t.toLocaleTimeString('en-GB', { hour12: false })}
    </div>
  )
}

/* ── Agent dashboard ────────────────────────────────────── */
function MainApp({ theme, onToggle }) {
  const [incidents,  setIncidents]  = useState([])
  const [liveStatus, setLiveStatus] = useState('connecting')
  const [agentName,  setAgentName]  = useState('')

  useEffect(() => {
    // Get agent name from localStorage set during login
    const user = JSON.parse(localStorage.getItem('resqnet_user') || '{}')
    setAgentName(user.name || user.email?.split('@')[0] || 'Agent')

    // Load incidents
    fetchIncidents().then(data => setIncidents(data))

    // Subscribe to realtime new incidents
    const ch = subscribeToIncidents(row =>
      setIncidents(prev => [row, ...prev])
    )
    ch.subscribe(s =>
      setLiveStatus(s === 'SUBSCRIBED' ? 'live' : 'connecting')
    )
    return () => supabase.removeChannel(ch)
  }, [])

  function handleSignOut() {
    localStorage.removeItem('resqnet_token')
    localStorage.removeItem('resqnet_user')
    window.location.href = '/login'
  }

  return (
    <div className="app">

      <header className="header">
        <div className="header-brand">
          <div className="brand-mark">
            <div className="brand-icon">
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                <path
                  d="M1 7 Q2.5 3 4 7 Q5.5 11 7 7 Q8.5 3 10 7 Q11.5 11 13 7"
                  stroke="var(--accent)" strokeWidth="1.5"
                  strokeLinecap="round" strokeLinejoin="round" fill="none"
                />
              </svg>
            </div>
            <span className="brand-name">RESQNET</span>
          </div>
          <div className="brand-sep" />
          <span className="brand-sub">Disaster Call Management</span>
        </div>

        <div className="header-right">
          {agentName && (
            <div className="agent-pill">Agent: {agentName}</div>
          )}
          <div className={`signal-status ${liveStatus}`}>
            <span className="signal-dot" />
            {liveStatus === 'live' ? 'Signal Active' : 'Connecting...'}
          </div>
          <Clock />
          <ThemeToggle theme={theme} onToggle={onToggle} />
          <button className="signout-btn" onClick={handleSignOut}>
            Sign Out
          </button>
        </div>
      </header>

      <StatsBar incidents={incidents} />

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

/* ── Root ───────────────────────────────────────────────── */
export default function App() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem('resqnet-theme') || 'dark'
  )

  useEffect(() => {
    document.documentElement.className = theme
    localStorage.setItem('resqnet-theme', theme)
  }, [theme])

  const toggleTheme = () =>
    setTheme(prev => prev === 'dark' ? 'light' : 'dark')

  return (
    <Routes>
      <Route
        path="/login"
        element={<Login theme={theme} onToggle={toggleTheme} />}
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <MainApp theme={theme} onToggle={toggleTheme} />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}