import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { attachAgentToken } from '../lib/supabaseClient'
import { clearAuthSession, getAuthToken } from '../lib/api'
import { API_URL } from '../lib/config'

export default function ProtectedRoute({ children }) {
  const [status, setStatus] = useState('checking') // checking | ok | denied

  useEffect(() => {
    // JWT lives in sessionStorage (tab-scoped). If the tab was just opened
    // or the user signed out, there is no token and we bounce to /login.
    const token = getAuthToken()

    if (!token) {
      setStatus('denied')
      return
    }

    attachAgentToken(token)

    fetch(`${API_URL}/api/auth/session`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => {
        if (!res.ok) {
          // Token was rejected by the backend (expired/revoked). Clear it so
          // the next mount doesn't loop trying the same dead token.
          clearAuthSession()
          setStatus('denied')
          return
        }
        setStatus('ok')
      })
      .catch(() => setStatus('denied'))
  }, [])

  if (status === 'checking') {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg-root)', color: 'var(--txt-muted)',
        fontFamily: 'Chakra Petch, sans-serif',
        fontSize: 11, letterSpacing: '0.14em'
      }}>
        AUTHENTICATING...
      </div>
    )
  }

  return status === 'ok' ? children : <Navigate to="/login" replace />
}