import { Route, Routes } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import { AuthProvider } from './providers/AuthProvider'

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<LandingPage />} />
      </Routes>
    </AuthProvider>
  )
}

export default App
