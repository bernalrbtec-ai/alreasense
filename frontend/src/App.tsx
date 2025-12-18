import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import { useEffect, lazy, Suspense } from 'react'
import { api } from './lib/api'
import { Toaster } from 'sonner'
import { lazyLoadWithRetry } from './utils/lazyLoadWithRetry'

// ✅ CRITICAL FIX: Lazy loading de páginas para reduzir bundle inicial
// Login page - sempre carregar (primeira página)
import LoginPage from './pages/LoginPage'

// Lazy load de todas as outras páginas
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const MessagesPage = lazy(() => import('./pages/MessagesPage'))
const CampaignLogsPage = lazy(() => import('./pages/CampaignLogsPage'))
const ConnectionsPage = lazy(() => import('./pages/ConnectionsPage'))
const ExperimentsPage = lazy(() => import('./pages/ExperimentsPage'))
const BillingPage = lazy(() => import('./pages/BillingPage'))
const TenantsPage = lazy(() => import('./pages/TenantsPage'))
const ProductsPage = lazy(() => import('./pages/ProductsPage'))
const PlansPage = lazy(() => import('./pages/PlansPage'))
const SystemStatusPage = lazy(() => import('./pages/SystemStatusPage'))
const EvolutionConfigPage = lazy(() => import('./pages/EvolutionConfigPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'))
// ConfigurationsPage com retry para resolver problemas de carregamento em produção
const ConfigurationsPage = lazyLoadWithRetry(() => import('./pages/ConfigurationsPage'), 3, 1000)
const ContactsPage = lazy(() => import('./pages/ContactsPage'))
const CampaignsPage = lazy(() => import('./pages/CampaignsPage'))
const WebhookMonitoringPage = lazy(() => import('./pages/WebhookMonitoringPage'))
const TestPresencePage = lazy(() => import('./pages/TestPresencePage'))
const DepartmentsPage = lazy(() => import('./pages/DepartmentsPage'))
const QuickRepliesPage = lazy(() => import('./pages/QuickRepliesPage'))
// AgendaPage com retry para resolver problemas de carregamento em produção
const AgendaPage = lazyLoadWithRetry(() => import('./pages/AgendaPage'), 3, 1000)
const ChatPage = lazy(() => import('./modules/chat').then(module => ({ default: module.ChatPage })))
// Billing API Pages
const BillingApiPage = lazy(() => import('./pages/BillingApiPage'))
const BillingApiKeysPage = lazy(() => import('./pages/BillingApiKeysPage'))
const BillingApiTemplatesPage = lazy(() => import('./pages/BillingApiTemplatesPage'))
const BillingApiCampaignsPage = lazy(() => import('./pages/BillingApiCampaignsPage'))
const IntegracaoPage = lazy(() => import('./pages/IntegracaoPage'))

// Components
import Layout from './components/Layout'
import LoadingSpinner from './components/ui/LoadingSpinner'
import ErrorBoundary from './components/ErrorBoundary'
import { ProtectedRoute } from './components/ProtectedRoute'
import { ProtectedAgendaRoute } from './components/ProtectedAgendaRoute'
import { ProtectedChatRoute } from './components/ProtectedChatRoute'
import { ProtectedContactsRoute } from './components/ProtectedContactsRoute'
import { useTheme } from './hooks/useTheme'

function App() {
  const { user, token, isLoading, checkAuth } = useAuthStore()
  
  // ✅ Inicializar tema (aplica classe dark no HTML)
  useTheme()

  useEffect(() => {
    // ✅ FIX: Sempre verificar autenticação ao montar o componente
    // Isso garante que após F5, o token seja verificado e restaurado
    checkAuth()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])  // ✅ Executar apenas uma vez ao montar (checkAuth já gerencia token)
  
  useEffect(() => {
    // ✅ Set axios token if it exists (importante manter após mudança de página)
    // Executar sempre que token mudar (após login, logout, etc)
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`
      console.log('✅ [AUTH] Token configurado no axios')
    } else {
      delete api.defaults.headers.common['Authorization']
      console.log('✅ [AUTH] Token removido do axios')
    }
  }, [token])

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
          
          {/* ✅ Agente: Chat, Agenda e Contatos */}
          {isAgente ? (
            <>
              <Route path="chat" element={
                <ProtectedChatRoute>
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <ChatPage />
                  </Suspense>
                </ProtectedChatRoute>
              } />
              <Route path="agenda" element={
                <ProtectedAgendaRoute>
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <AgendaPage />
                  </Suspense>
                </ProtectedAgendaRoute>
              } />
              <Route path="contacts" element={
                <ProtectedContactsRoute>
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <ContactsPage />
                  </Suspense>
                </ProtectedContactsRoute>
              } />
              <Route path="profile" element={
                <Suspense fallback={<LoadingSpinner size="lg" />}>
                  <ProfilePage />
                </Suspense>
              } />
              <Route path="*" element={<Navigate to="/chat" replace />} />
            </>
          ) : (
            <>
              <Route path="dashboard" element={
                <Suspense fallback={<LoadingSpinner size="lg" />}>
                  <DashboardPage />
                </Suspense>
              } />
              <Route path="billing" element={
                <Suspense fallback={<LoadingSpinner size="lg" />}>
                  <BillingPage />
                </Suspense>
              } />
              <Route path="profile" element={
                <Suspense fallback={<LoadingSpinner size="lg" />}>
                  <ProfilePage />
                </Suspense>
              } />
              <Route path="configurations" element={
                <Suspense fallback={<LoadingSpinner size="lg" />}>
                  <ConfigurationsPage />
                </Suspense>
              } />
              
              {/* Workflow - Chat e Agenda */}
              <Route path="chat" element={
                <ProtectedChatRoute>
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <ChatPage />
                  </Suspense>
                </ProtectedChatRoute>
              } />
              <Route path="agenda" element={
                <ProtectedAgendaRoute>
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <AgendaPage />
                  </Suspense>
                </ProtectedAgendaRoute>
              } />
              <Route path="quick-replies" element={
                <ProtectedChatRoute>
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <QuickRepliesPage />
                  </Suspense>
                </ProtectedChatRoute>
              } />
              
              {/* Rotas Protegidas por Produto */}
              <Route path="contacts" element={
                <ProtectedRoute requiredProduct="flow">
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <ContactsPage />
                  </Suspense>
                </ProtectedRoute>
              } />
              <Route path="campaigns" element={
                <ProtectedRoute requiredProduct="flow">
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <CampaignsPage />
                  </Suspense>
                </ProtectedRoute>
              } />
              <Route path="campaigns/logs" element={
                <ProtectedRoute requiredProduct="flow">
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <CampaignLogsPage />
                  </Suspense>
                </ProtectedRoute>
              } />
              <Route path="campaigns/test-presence" element={
                <ProtectedRoute requiredProduct="flow">
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <TestPresencePage />
                  </Suspense>
                </ProtectedRoute>
              } />
              <Route path="connections" element={
                <ProtectedRoute requiredProduct="flow">
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <ConnectionsPage />
                  </Suspense>
                </ProtectedRoute>
              } />
              <Route path="experiments" element={
                <ProtectedRoute requiredProduct="sense">
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <ExperimentsPage />
                  </Suspense>
                </ProtectedRoute>
              } />
              
              {/* Notificações - Acesso para usuários com Flow */}
              <Route path="admin/notifications" element={
                <ProtectedRoute requiredProduct="flow">
                  <Suspense fallback={<LoadingSpinner size="lg" />}>
                    <NotificationsPage />
                  </Suspense>
                </ProtectedRoute>
              } />
              
              {/* Billing API Routes */}
              <Route path="billing-api" element={
                <Suspense fallback={<LoadingSpinner size="lg" />}>
                  <BillingApiPage />
                </Suspense>
              } />
              <Route path="billing-api/keys" element={
                <Suspense fallback={<LoadingSpinner size="lg" />}>
                  <BillingApiKeysPage />
                </Suspense>
              } />
              <Route path="billing-api/templates" element={
                <Suspense fallback={<LoadingSpinner size="lg" />}>
                  <BillingApiTemplatesPage />
                </Suspense>
              } />
              <Route path="billing-api/campaigns" element={
                <Suspense fallback={<LoadingSpinner size="lg" />}>
                  <BillingApiCampaignsPage />
                </Suspense>
              } />
              
              {/* Integração Routes */}
              <Route path="integracao" element={
                <Suspense fallback={<LoadingSpinner size="lg" />}>
                  <IntegracaoPage />
                </Suspense>
              } />
              
              {/* Super Admin Routes */}
              {isSuperAdmin && (
                <>
                  <Route path="admin/tenants" element={
                    <Suspense fallback={<LoadingSpinner size="lg" />}>
                      <TenantsPage />
                    </Suspense>
                  } />
                  <Route path="admin/products" element={
                    <Suspense fallback={<LoadingSpinner size="lg" />}>
                      <ProductsPage />
                    </Suspense>
                  } />
                  <Route path="admin/plans" element={
                    <Suspense fallback={<LoadingSpinner size="lg" />}>
                      <PlansPage />
                    </Suspense>
                  } />
                  <Route path="admin/system" element={
                    <Suspense fallback={<LoadingSpinner size="lg" />}>
                      <SystemStatusPage />
                    </Suspense>
                  } />
                  <Route path="admin/evolution" element={
                    <Suspense fallback={<LoadingSpinner size="lg" />}>
                      <EvolutionConfigPage />
                    </Suspense>
                  } />
                  <Route path="admin/webhook-monitoring" element={
                    <Suspense fallback={<LoadingSpinner size="lg" />}>
                      <WebhookMonitoringPage />
                    </Suspense>
                  } />
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
