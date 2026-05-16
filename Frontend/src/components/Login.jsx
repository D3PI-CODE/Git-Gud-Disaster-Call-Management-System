import { useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Login() {
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  async function handleLogin(e) {
    e.preventDefault()
    setLoading(true); setError('')
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) { setError(error.message); setLoading(false) }
    else window.location.assign('/dashboard')
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-root)'
    }}>
      <div style={{
        width: 360, padding: '36px 32px',
        background: 'var(--bg-card)',
        border: '1px solid var(--border-mid)',
        borderRadius: 12
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 10, margin: '0 auto 12px',
            background: 'var(--lime-dim)', border: '1.5px solid var(--lime-border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <svg width="18" height="18" viewBox="0 0 14 14" fill="none">
              <path d="M1 7 Q2.5 3 4 7 Q5.5 11 7 7 Q8.5 3 10 7 Q11.5 11 13 7"
                stroke="#A8FF3E" strokeWidth="1.5" strokeLinecap="round"
                strokeLinejoin="round" fill="none"/>
            </svg>
          </div>
          <div style={{
            fontFamily: 'var(--font-display)', fontSize: 18,
            fontWeight: 700, letterSpacing: '0.18em', color: 'var(--txt-primary)'
          }}>RESQNET</div>
          <div style={{
            fontFamily: 'var(--font-display)', fontSize: 10,
            letterSpacing: '0.14em', color: 'var(--txt-muted)',
            textTransform: 'uppercase', marginTop: 4
          }}>Agent Portal</div>
        </div>

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="form-row">
            <label className="form-label">Agent Email</label>
            <input className="form-input" type="email" placeholder="agent@resqnet.lk"
              value={email} onChange={e => setEmail(e.target.value)} required />
          </div>
          <div className="form-row">
            <label className="form-label">Password</label>
            <input className="form-input" type="password" placeholder="••••••••"
              value={password} onChange={e => setPassword(e.target.value)} required />
          </div>

          {error && <div className="error-banner">⚠ {error}</div>}

          <button className="submit-btn" type="submit" disabled={loading}>
            {loading ? '⏳  Signing in...' : '→  Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}