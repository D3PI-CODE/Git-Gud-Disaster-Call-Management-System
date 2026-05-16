import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

// Apply theme BEFORE React renders — prevents any flash of wrong theme
const savedTheme = localStorage.getItem('resqnet-theme') || 'dark'
document.documentElement.className = savedTheme

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
)