import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function ProtectedRoute({ children }) {
  const [status, setStatus] = useState('checking') // checking | ok | denied

  useEffect(() => {
    const token = localStorage.getItem('resqnet_token')

    if (!token) {
      setStatus('denied')
      return
    }

    // Verify token is still valid with the backend
    fetch(`${API_URL}/api/auth/session`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => setStatus(res.ok ? 'ok' : 'denied'))
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