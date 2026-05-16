import { useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Login() {
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const [isSignUp, setIsSignUp] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true); setError('')
    
    if (isSignUp) {
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) { setError(error.message); setLoading(false) }
      else {
        setError('Check your email to confirm sign up (or sign in if auto-confirm is enabled).')
        setLoading(false)
      }
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) { setError(error.message); setLoading(false) }
      else window.location.assign('/dashboard')
    }
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

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
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

          {error && <div className="error-banner" style={{ background: error.includes('Check your email') ? 'var(--lime-dim)' : undefined, color: error.includes('Check your email') ? 'var(--lime-base)' : undefined, borderColor: error.includes('Check your email') ? 'var(--lime-border)' : undefined }}>
            {error.includes('Check your email') ? '✓ ' : '⚠ '} {error}
          </div>}

          <button className="submit-btn" type="submit" disabled={loading}>
            {loading ? '⏳  Processing...' : (isSignUp ? '→  Sign Up' : '→  Sign In')}
          </button>
          
          <div style={{ textAlign: 'center', marginTop: 12 }}>
            <button 
              type="button" 
              onClick={() => { setIsSignUp(!isSignUp); setError(''); }}
              style={{ background: 'none', border: 'none', color: 'var(--txt-muted)', fontSize: 12, cursor: 'pointer', textDecoration: 'underline' }}
            >
              {isSignUp ? 'Already have an account? Sign In' : 'Need an account? Sign Up'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}