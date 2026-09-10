import { useState, useEffect } from 'react'
import { Route, Routes } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import AuthPage from './pages/AuthPage'
import StudioPage from './pages/StudioPage'
import ProjectsPage from './pages/ProjectsPage'
import { AuthProvider } from './providers/AuthProvider'
import { ProtectedRoute } from './components/ProtectedRoute'
import { DisclaimerModal } from './components/DisclaimerModal'

function App() {
  const [showDisclaimer, setShowDisclaimer] = useState(false)

  useEffect(() => {
    // Show disclaimer popup when the site is opened if not dismissed in current session
    const dismissed = sessionStorage.getItem('higenbot_disclaimer_dismissed')
    if (!dismissed) {
      setShowDisclaimer(true)
    }
  }, [])

  const handleDismissDisclaimer = () => {
    sessionStorage.setItem('higenbot_disclaimer_dismissed', 'true')
    setShowDisclaimer(false)
  }

  return (
    <AuthProvider>
      {showDisclaimer && (
        <DisclaimerModal
          onConfirm={handleDismissDisclaimer}
          onCancel={handleDismissDisclaimer}
        />
      )}
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<AuthPage />} />
        <Route
          path="/studio"
          element={
            <ProtectedRoute>
              <StudioPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/studio/:runId"
          element={
            <ProtectedRoute>
              <StudioPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects"
          element={
            <ProtectedRoute>
              <ProjectsPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </AuthProvider>
  )
}

export default App
