import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function ThemeToggle({ theme, onToggle }) {
  return (
    <button className="theme-toggle" onClick={onToggle}
      title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}>
      {theme === 'dark' ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1"  x2="12" y2="3"/>
          <line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22"   x2="5.64"  y2="5.64"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1"  y1="12" x2="3"  y2="12"/>
          <line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22"  y1="19.78" x2="5.64"  y2="18.36"/>
          <line x1="18.36" y1="5.64"  x2="19.78" y2="4.22"/>
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      )}
    </button>
  )
}

export default function Login({ theme, onToggle }) {
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const navigate = useNavigate()

  async function handleLogin(e) {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email, password }),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.detail || 'Invalid email or password')
        setLoading(false)
        return
      }

      // Save token and user info to localStorage
      localStorage.setItem('resqnet_token', data.access_token)
      localStorage.setItem('resqnet_user',  JSON.stringify(data.user))

      navigate('/dashboard')
    } catch (err) {
      setError('Could not connect to server. Is the backend running?')
      setLoading(false)
    }
  }

  return (
    <div className="login-page">

      {/* Left: Brand panel (always dark) */}
      <div className="login-brand">
        <div className="brand-logo">
          <div className="brand-icon-box">
            <svg width="16" height="16" viewBox="0 0 14 14" fill="none">
              <path d="M1 7 Q2.5 3 4 7 Q5.5 11 7 7 Q8.5 3 10 7 Q11.5 11 13 7"
                stroke="#A8FF3E" strokeWidth="1.5" strokeLinecap="round"
                strokeLinejoin="round" fill="none"/>
            </svg>
          </div>
          <span className="brand-wordmark">RESQNET</span>
        </div>

        <div className="brand-center">
          <h2 className="brand-tagline">
            Faster <span>response.</span><br />
            Smarter <span>triage.</span>
          </h2>
          <p className="brand-desc">
            AI-powered disaster call management for Sri Lanka's emergency response teams.
          </p>
          <div className="signal-wave">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="signal-bar" />
            ))}
          </div>
        </div>

        <div className="brand-stats">
          <div className="brand-stat">
            <div className="brand-stat-dot" />
            Voice calls analysed by VALSEA AI
          </div>
          <div className="brand-stat">
            <div className="brand-stat-dot" />
            Priority scored in under 30 seconds
          </div>
          <div className="brand-stat">
            <div className="brand-stat-dot" />
            Live sync to all active agents
          </div>
        </div>
      </div>

      {/* Right: Form panel */}
      <div className="login-form-panel">
        <div className="login-theme-toggle">
          <ThemeToggle theme={theme} onToggle={onToggle} />
        </div>

        <div className="login-form-inner">
          <div className="login-greeting">
            <h1>Welcome back</h1>
            <p>Sign in to your ResQNet agent portal</p>
          </div>

          <form onSubmit={handleLogin} className="login-fields">
            <div className="form-row">
              <label className="form-label">Agent Email</label>
              <input
                className="form-input"
                type="email"
                placeholder="agent@resqnet.lk"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-row">
              <label className="form-label">Password</label>
              <input
                className="form-input"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
            </div>

            {error && <div className="error-banner">⚠ {error}</div>}

            <button className="submit-btn" type="submit" disabled={loading}
              style={{ marginTop: 4 }}>
              {loading ? '⏳  Signing in...' : '→  Sign In'}
            </button>
          </form>

          <p className="login-telegram-note">
            Victims report via Telegram · No login needed
          </p>
        </div>
      </div>

    </div>
  )
}