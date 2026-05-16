import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { getAuthToken, getSession } from '../lib/api'

export default function ProtectedRoute({ children }) {
  const [authed, setAuthed] = useState(undefined)

  useEffect(() => {
    const token = getAuthToken()
    if (!token) {
      setAuthed(false)
      return
    }
    getSession()
      .then(() => setAuthed(true))
      .catch(() => setAuthed(false))
  }, [])

  if (authed === undefined) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', color: 'var(--txt-muted)',
        fontFamily: 'var(--font-display)', letterSpacing: '0.1em', fontSize: 12,
      }}>
        AUTHENTICATING...
      </div>
    )
  }

  return authed ? children : <Navigate to="/login" replace />
}
