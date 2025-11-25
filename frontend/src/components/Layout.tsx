import { useState, useMemo } from 'react'
import { Link, useLocation, Outlet } from 'react-router-dom'
import { 
  LayoutDashboard, 
  MessageSquare, 
  Wifi, 
  FlaskConical, 
  CreditCard,
  Menu,
  X,
  LogOut,
  User,
  Users,
  Package,
  Activity,
  Server,
  ChevronLeft,
  ChevronRight,
  Settings,
  Database,
  Calendar
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useTenantProducts } from '../hooks/useTenantProducts'
import { useUserAccess } from '../hooks/useUserAccess'
import { useTenantSocket } from '../modules/chat/hooks/useTenantSocket'
import { Button } from './ui/Button'
import Logo from './ui/Logo'
import Avatar from './ui/Avatar'
import UserDropdown from './UserDropdown'
import { cn } from '../lib/utils'

// Mapeamento de produtos para itens do menu
const productMenuItems = {
  flow: [
    { name: 'Contatos', href: '/contacts', icon: Users, requiredProduct: 'flow' },
    { name: 'Campanhas', href: '/campaigns', icon: MessageSquare, requiredProduct: 'flow' },
  ],
  workflow: [
    { name: 'Chat', href: '/chat', icon: MessageSquare, requiredProduct: 'workflow' },
    { name: 'Agenda', href: '/agenda', icon: Calendar, requiredProduct: 'workflow' },
  ],
  sense: [
    { name: 'Contatos', href: '/contacts', icon: Users, requiredProduct: 'sense' },
    { name: 'Experimentos', href: '/experiments', icon: FlaskConical, requiredProduct: 'sense' },
  ],
  api_public: [
    { name: 'API Docs', href: '/api-docs', icon: Server, requiredProduct: 'api_public' },
  ],
}

const baseNavigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Planos', href: '/billing', icon: CreditCard },
  { name: 'Configurações', href: '/configurations', icon: Settings },
]

const adminNavigation = [
  { name: 'Clientes', href: '/admin/tenants', icon: Users },
  { name: 'Produtos', href: '/admin/products', icon: Package },
  { name: 'Planos', href: '/admin/plans', icon: CreditCard },
  { name: 'Status do Sistema', href: '/admin/system', icon: Activity },
  { name: 'Servidor de Instância', href: '/admin/evolution', icon: Server },
  { name: 'Monitoramento Webhooks', href: '/admin/webhook-monitoring', icon: Database },
]

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const { activeProductSlugs, loading: productsLoading } = useTenantProducts()
  const { hasProductAccess } = useUserAccess()
  
  // 🔔 WebSocket global do tenant - fica sempre conectado para receber notificações
  useTenantSocket()
  
  const isSuperAdmin = user?.is_superuser || user?.is_staff
  const isAgente = user?.role === 'agente' || user?.is_agente
  
  // Gerar navegação dinâmica baseada nos produtos ativos e acesso do usuário
  const navigation = useMemo(() => {
    // ✅ Agente: Chat e Agenda (se tiver acesso ao workflow)
    if (isAgente) {
      const workflowAccess = hasProductAccess('workflow')
      const items = []
      if (workflowAccess.canAccess) {
        items.push(
          { name: 'Chat', href: '/chat', icon: MessageSquare },
          { name: 'Agenda', href: '/agenda', icon: Calendar }
        )
      }
      return items
    }
    
    const items = [...baseNavigation]
    
    // Adicionar itens de menu dos produtos ativos, mas filtrar por acesso
    activeProductSlugs.forEach((productSlug) => {
      const productItems = productMenuItems[productSlug as keyof typeof productMenuItems]
      if (productItems) {
        // Filtrar itens baseado no acesso do usuário
        const accessibleItems = productItems.filter(item => {
          if (!item.requiredProduct) {
            return true
          }
          const access = hasProductAccess(item.requiredProduct)
          return access.canAccess
        })
        items.push(...accessibleItems)
      }
    })
    
    return items
  }, [activeProductSlugs, hasProductAccess, isAgente])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar */}
      <div className={cn(
        "fixed inset-0 z-modal lg:hidden",
        sidebarOpen ? "block" : "hidden"
      )}>
        <div className="fixed inset-0 bg-gray-600 bg-opacity-75" onClick={() => setSidebarOpen(false)} />
        <div className="relative flex w-full max-w-xs flex-1 flex-col bg-white">
          <div className="flex h-16 items-center justify-between px-4">
            <Logo size="sm" />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="h-6 w-6" />
            </Button>
          </div>
          <nav className="flex-1 space-y-1 px-2 py-4">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    "group flex items-center px-2 py-2 text-sm font-medium rounded-md",
                    isActive
                      ? "bg-brand-100 text-brand-700"
                      : "text-gray-600 hover:bg-brand-50 hover:text-brand-900"
                  )}
                  onClick={() => setSidebarOpen(false)}
                >
                  <item.icon className="mr-3 h-5 w-5" />
                  {item.name}
                </Link>
              )
            })}
            
            {/* Admin Section - Oculto para agentes */}
            {isSuperAdmin && !isAgente && (
              <>
                <div className="pt-4 pb-2">
                  <div className="px-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Administração
                  </div>
                </div>
                {adminNavigation.map((item) => {
                  const isActive = location.pathname === item.href
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={cn(
                        "group flex items-center px-2 py-2 text-sm font-medium rounded-md",
                        isActive
                          ? "bg-brand-100 text-brand-700"
                          : "text-gray-600 hover:bg-brand-50 hover:text-brand-900"
                      )}
                      onClick={() => setSidebarOpen(false)}
                    >
                      <item.icon className="mr-3 h-5 w-5" />
                      {item.name}
                    </Link>
                  )
                })}
              </>
            )}
          </nav>
        </div>
      </div>

      {/* Desktop sidebar */}
      <div className={cn(
        "hidden md:fixed md:inset-y-0 md:flex md:flex-col transition-all duration-300 z-sidebar",
        sidebarCollapsed ? "md:w-16" : "md:w-64"
      )}>
        <div className="flex flex-col flex-grow bg-white border-r border-gray-200">
          <div className="flex h-16 items-center justify-between px-4">
            {!sidebarCollapsed && <Logo size="sm" />}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="ml-auto"
            >
              {sidebarCollapsed ? (
                <ChevronRight className="h-5 w-5" />
              ) : (
                <ChevronLeft className="h-5 w-5" />
              )}
            </Button>
          </div>
          <nav className="flex-1 space-y-1 px-2 py-4 overflow-y-auto">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    "group flex items-center px-2 py-2 text-sm font-medium rounded-md",
                    isActive
                      ? "bg-brand-100 text-brand-700"
                      : "text-gray-600 hover:bg-brand-50 hover:text-brand-900"
                  )}
                  title={sidebarCollapsed ? item.name : undefined}
                >
                  <item.icon className={cn("h-5 w-5", !sidebarCollapsed && "mr-3")} />
                  {!sidebarCollapsed && item.name}
                </Link>
              )
            })}
            
            {/* Admin Section - Oculto para agentes */}
            {isSuperAdmin && !sidebarCollapsed && !isAgente && (
              <>
                <div className="pt-4 pb-2">
                  <div className="px-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    ADMIN
                  </div>
                </div>
                {adminNavigation.map((item) => {
                  const isActive = location.pathname === item.href
                  
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={cn(
                        "group flex items-center px-2 py-2 text-sm font-medium rounded-md",
                        isActive
                          ? "bg-brand-100 text-brand-700"
                          : "text-gray-600 hover:bg-brand-50 hover:text-brand-900"
                      )}
                    >
                      <item.icon className="mr-3 h-5 w-5" />
                      {item.name}
                    </Link>
                  )
                })}
              </>
            )}
          </nav>
          
          {/* User info */}
          <div className="border-t border-gray-200 p-4">
            {sidebarCollapsed ? (
              <div className="flex flex-col items-center space-y-2">
                <Avatar 
                  name={`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username || 'Usuário'} 
                  size="md" 
                />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={logout}
                  title="Sair"
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <Avatar 
                    name={`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username || 'Usuário'} 
                    size="md" 
                  />
                  <div className="ml-3 flex-1">
                    <p className="text-sm font-medium text-gray-700">{`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username}</p>
                    <p className="text-xs text-gray-500">{user?.tenant?.name}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={logout}
                  className="ml-2"
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className={cn(
        "transition-all duration-300",
        sidebarCollapsed ? "md:pl-16" : "md:pl-64"
      )}>
        {/* Top bar */}
        <div className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 bg-white px-3 shadow-sm sm:gap-x-6 sm:px-4 md:px-6 lg:px-8">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5 sm:h-6 sm:w-6" />
          </Button>
          
          <div className="flex flex-1 gap-x-4 self-stretch lg:gap-x-6">
            <div className="flex flex-1" />
            <div className="flex items-center gap-x-4 lg:gap-x-6">
              <div className="hidden lg:block lg:h-6 lg:w-px lg:bg-gray-200" />
              <div className="flex items-center gap-x-2">
                <UserDropdown />
              </div>
            </div>
          </div>
        </div>

        {/* Page content */}
        {location.pathname === '/chat' ? (
          <main className="p-0 h-[calc(100vh-64px)] overflow-hidden">
            <Outlet />
          </main>
        ) : (
          <main className="py-4 sm:py-6">
            <div className="mx-auto max-w-7xl px-3 sm:px-4 md:px-6 lg:px-8">
              <Outlet />
            </div>
          </main>
        )}
      </div>
    </div>
  )
}
