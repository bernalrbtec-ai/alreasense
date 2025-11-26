import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import { useEffect } from 'react'
import { api } from './lib/api'
import { Toaster } from 'sonner'

// Pages
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import MessagesPage from './pages/MessagesPage'
import CampaignLogsPage from './pages/CampaignLogsPage'
import ConnectionsPage from './pages/ConnectionsPage'
import ExperimentsPage from './pages/ExperimentsPage'
import BillingPage from './pages/BillingPage'
import TenantsPage from './pages/TenantsPage'
import ProductsPage from './pages/ProductsPage'
import PlansPage from './pages/PlansPage'
import SystemStatusPage from './pages/SystemStatusPage'
import EvolutionConfigPage from './pages/EvolutionConfigPage'
import ProfilePage from './pages/ProfilePage'
import NotificationsPage from './pages/NotificationsPage'
import ConfigurationsPage from './pages/ConfigurationsPage'
import ContactsPage from './pages/ContactsPage'
import CampaignsPage from './pages/CampaignsPage'
import WebhookMonitoringPage from './pages/WebhookMonitoringPage'
import TestPresencePage from './pages/TestPresencePage'
import DepartmentsPage from './pages/DepartmentsPage'
import AgendaPage from './pages/AgendaPage'
import { ChatPage } from './modules/chat'

// Components
import Layout from './components/Layout'
import LoadingSpinner from './components/ui/LoadingSpinner'
import ErrorBoundary from './components/ErrorBoundary'
import { ProtectedRoute } from './components/ProtectedRoute'
import { ProtectedAgendaRoute } from './components/ProtectedAgendaRoute'
import { ProtectedChatRoute } from './components/ProtectedChatRoute'

function App() {
  const { user, token, isLoading, checkAuth } = useAuthStore()

  useEffect(() => {
    // ✅ Set axios token if it exists (importante manter após mudança de página)
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`
    }
    
    // ✅ Check auth on mount and when token changes
    // Importante verificar token em todas as navegações para evitar perda de autenticação
    // ✅ FIX: Usar apenas token como dependência para evitar loop infinito
    checkAuth()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])  // ✅ Apenas token como dependência (checkAuth é estável do Zustand)

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
  const isAgente = user?.role === 'agente' || user?.is_agente

  return (
    <ErrorBoundary>
      <Toaster 
        position="top-right"
        expand={false}
        richColors
        closeButton
        duration={4000}
        toastOptions={{
          style: {
            fontSize: '14px',
            maxWidth: '400px',
          },
        }}
      />
      <Routes>
        {/* Todas as rotas - COM Layout */}
        <Route path="/" element={<Layout />}>
          {/* ✅ Agente: Redirecionar para /chat se tentar acessar outras rotas */}
          <Route index element={<Navigate to={isAgente ? "/chat" : "/dashboard"} replace />} />
          
          {/* ✅ Agente: Apenas Chat e Perfil */}
          {isAgente ? (
            <>
              <Route path="chat" element={
                <ProtectedChatRoute>
                  <ChatPage />
                </ProtectedChatRoute>
              } />
              <Route path="agenda" element={
                <ProtectedAgendaRoute>
                  <AgendaPage />
                </ProtectedAgendaRoute>
              } />
              <Route path="profile" element={<ProfilePage />} />
              <Route path="*" element={<Navigate to="/chat" replace />} />
            </>
          ) : (
            <>
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="billing" element={<BillingPage />} />
              <Route path="profile" element={<ProfilePage />} />
              <Route path="configurations" element={<ConfigurationsPage />} />
              
              {/* Workflow - Chat e Agenda */}
              <Route path="chat" element={
                <ProtectedChatRoute>
                  <ChatPage />
                </ProtectedChatRoute>
              } />
              <Route path="agenda" element={
                <ProtectedAgendaRoute>
                  <AgendaPage />
                </ProtectedAgendaRoute>
              } />
              
              {/* Rotas Protegidas por Produto */}
              <Route path="contacts" element={
                <ProtectedRoute requiredProduct="flow">
                  <ContactsPage />
                </ProtectedRoute>
              } />
              <Route path="campaigns" element={
                <ProtectedRoute requiredProduct="flow">
                  <CampaignsPage />
                </ProtectedRoute>
              } />
              <Route path="campaigns/logs" element={
                <ProtectedRoute requiredProduct="flow">
                  <CampaignLogsPage />
                </ProtectedRoute>
              } />
              <Route path="campaigns/test-presence" element={
                <ProtectedRoute requiredProduct="flow">
                  <TestPresencePage />
                </ProtectedRoute>
              } />
              <Route path="connections" element={
                <ProtectedRoute requiredProduct="flow">
                  <ConnectionsPage />
                </ProtectedRoute>
              } />
              <Route path="experiments" element={
                <ProtectedRoute requiredProduct="sense">
                  <ExperimentsPage />
                </ProtectedRoute>
              } />
              
              {/* Notificações - Acesso para usuários com Flow */}
              <Route path="admin/notifications" element={
                <ProtectedRoute requiredProduct="flow">
                  <NotificationsPage />
                </ProtectedRoute>
              } />
              
              {/* Super Admin Routes */}
              {isSuperAdmin && (
                <>
                  <Route path="admin/tenants" element={<TenantsPage />} />
                  <Route path="admin/products" element={<ProductsPage />} />
                  <Route path="admin/plans" element={<PlansPage />} />
                  <Route path="admin/system" element={<SystemStatusPage />} />
                  <Route path="admin/evolution" element={<EvolutionConfigPage />} />
                  <Route path="admin/webhook-monitoring" element={<WebhookMonitoringPage />} />
                </>
              )}
              
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </>
          )}
        </Route>
      </Routes>
    </ErrorBoundary>
  )
}

export default App
