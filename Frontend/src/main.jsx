import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'

// Apply theme before React renders — prevents flash
const savedTheme = localStorage.getItem('resqnet-theme') || 'dark'
document.documentElement.className = savedTheme

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
)