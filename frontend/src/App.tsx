import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import { useEffect } from 'react'
import { api } from './lib/api'

// Pages
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import MessagesPage from './pages/MessagesPage'
import ConnectionsPage from './pages/ConnectionsPage'
import ExperimentsPage from './pages/ExperimentsPage'
import BillingPage from './pages/BillingPage'
import TenantsPage from './pages/TenantsPage'
import PlansPage from './pages/PlansPage'
import SystemStatusPage from './pages/SystemStatusPage'
import EvolutionConfigPage from './pages/EvolutionConfigPage'
import ProfilePage from './pages/ProfilePage'

// Components
import Layout from './components/Layout'
import LoadingSpinner from './components/ui/LoadingSpinner'
import ErrorBoundary from './components/ErrorBoundary'

function App() {
  const { user, token, isLoading, checkAuth } = useAuthStore()

  useEffect(() => {
    // Set axios token if it exists
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`
    }
    
    // Check auth only once on mount
    checkAuth()
  }, [])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  const isSuperAdmin = user?.is_superuser || user?.is_staff

  return (
    <ErrorBoundary>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/messages" element={<MessagesPage />} />
          <Route path="/connections" element={<ConnectionsPage />} />
          <Route path="/experiments" element={<ExperimentsPage />} />
          <Route path="/billing" element={<BillingPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          
          {/* Super Admin Routes */}
          {isSuperAdmin && (
            <>
              <Route path="/admin/tenants" element={<TenantsPage />} />
              <Route path="/admin/plans" element={<PlansPage />} />
              <Route path="/admin/system" element={<SystemStatusPage />} />
              <Route path="/admin/evolution" element={<EvolutionConfigPage />} />
            </>
          )}
          
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Layout>
    </ErrorBoundary>
  )
}

export default App
