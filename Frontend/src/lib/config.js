/** Production Railway API (used when Vercel still has localhost in VITE_API_URL). */
export const PRODUCTION_API_URL =
  'https://git-gud-disaster-call-management-system-production.up.railway.app'

const configured = (import.meta.env.VITE_API_URL || '').trim()
const pointsAtLocalhost =
  !configured ||
  configured === 'http://localhost:8000' ||
  configured.startsWith('http://127.0.0.1:')

export const API_URL =
  import.meta.env.PROD && pointsAtLocalhost
    ? PRODUCTION_API_URL
    : configured || 'http://localhost:8000'
