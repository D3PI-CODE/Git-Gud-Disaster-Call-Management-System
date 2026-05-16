import { useState } from 'react'
import { agentLogin, agentSignup } from '../lib/api'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isSignUp, setIsSignUp] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      if (isSignUp) {
        await agentSignup(email, password, name || email.split('@')[0])
      } else {
        await agentLogin(email, password)
      }
      window.location.assign('/dashboard')
    } catch (err) {
      setError(err.message || 'Authentication failed')
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-root)'
    }}>
      <div style={{
        width: 380, padding: '36px 32px',
        background: 'var(--bg-card)',
        border: '1px solid var(--border-mid)',
        borderRadius: 12
      }}>
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

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {isSignUp && (
            <div className="form-row">
              <label className="form-label">Agent Name</label>
              <input className="form-input" type="text" placeholder="Agent name"
                value={name} onChange={e => setName(e.target.value)} />
            </div>
          )}
          <div className="form-row">
            <label className="form-label">Agent Email</label>
            <input className="form-input" type="email" placeholder="agent@resqnet.lk"
              value={email} onChange={e => setEmail(e.target.value)} required />
          </div>
          <div className="form-row">
            <label className="form-label">Password</label>
            <input className="form-input" type="password" placeholder="••••••••"
              value={password} onChange={e => setPassword(e.target.value)} required minLength={6} />
          </div>

          {error && (
            <div className="error-banner">⚠ {error}</div>
          )}

          <button className="submit-btn" type="submit" disabled={loading}>
            {loading ? '⏳  Processing...' : (isSignUp ? '→  Create Agent Account' : '→  Sign In')}
          </button>

          <div style={{ textAlign: 'center', marginTop: 12 }}>
            <button
              type="button"
              onClick={() => { setIsSignUp(!isSignUp); setError('') }}
              style={{ background: 'none', border: 'none', color: 'var(--txt-muted)', fontSize: 12, cursor: 'pointer', textDecoration: 'underline' }}
            >
              {isSignUp ? 'Already have an account? Sign In' : 'Need an agent account? Sign Up'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
