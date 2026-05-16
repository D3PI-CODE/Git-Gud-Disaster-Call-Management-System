import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import Login from './components/Login.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/dashboard"
          element={(
            <ProtectedRoute>
              <App />
            </ProtectedRoute>
          )}
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
