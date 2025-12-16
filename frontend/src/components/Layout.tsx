import { useState, useMemo, useRef, useEffect } from 'react'
import { Link, useLocation, Outlet } from 'react-router-dom'
import { 
  LayoutDashboard, 
  MessageSquare, 
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
  Calendar,
  Lock,
  ChevronDown,
  Zap
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useTenantProducts } from '../hooks/useTenantProducts'
import { useUserAccess } from '../hooks/useUserAccess'
import { usePermissions } from '../hooks/usePermissions'
import { useTenantSocket } from '../modules/chat/hooks/useTenantSocket'
import { Button } from './ui/Button'
import Logo from './ui/Logo'
import Avatar from './ui/Avatar'
import ChangePasswordModal from './modals/ChangePasswordModal'
import { cn } from '../lib/utils'

// Mapeamento de produtos para itens do menu
const productMenuItems = {
  flow: [
    { name: 'Contatos', href: '/contacts', icon: Users, requiredProduct: 'flow' },
    { name: 'Campanhas', href: '/campaigns', icon: MessageSquare, requiredProduct: 'flow' },
  ],
  workflow: [
    { name: 'Chat', href: '/chat', icon: MessageSquare, requiredProduct: 'workflow' },
    { name: 'Respostas Rápidas', href: '/quick-replies', icon: Zap, requiredProduct: 'workflow' },
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
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [userDropdownOpen, setUserDropdownOpen] = useState(false)
  const userDropdownRef = useRef<HTMLDivElement>(null)
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const { activeProductSlugs } = useTenantProducts()
  const { hasProductAccess, canAccessAgenda, canAccessChat, canAccessContacts } = useUserAccess()
  
  // 🔔 WebSocket global do tenant - fica sempre conectado para receber notificações
  useTenantSocket()
  
  const isSuperAdmin = user?.is_superuser || user?.is_staff
  const { isAdmin, isGerente, isAgente } = usePermissions()
  
  // Fechar dropdown quando clicar fora
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userDropdownRef.current && !userDropdownRef.current.contains(event.target as Node)) {
        setUserDropdownOpen(false)
      }
    }

    if (userDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => {
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }
  }, [userDropdownOpen])
  
  // Gerar navegação dinâmica baseada nos produtos ativos e acesso do usuário
  const navigation = useMemo(() => {
    // ✅ Admin/Gerente/Agente: Chat, Agenda e Contatos sempre visíveis
    // (esses roles sempre têm acesso ao chat, então sempre têm acesso à agenda e contatos)
    if (isAdmin || isGerente || isAgente) {
      const items = [
        { name: 'Chat', href: '/chat', icon: MessageSquare },
        { name: 'Agenda', href: '/agenda', icon: Calendar },
        { name: 'Contatos', href: '/contacts', icon: Users }
      ]
      
      // Adicionar baseNavigation para admin/gerente (agente só vê chat/agenda)
      if (isAdmin || isGerente) {
        items.unshift(...baseNavigation)
      }
      
      // Adicionar itens de menu dos produtos ativos para admin/gerente
      if (isAdmin || isGerente) {
        (activeProductSlugs || []).forEach((productSlug) => {
          const productItems = productMenuItems[productSlug as keyof typeof productMenuItems]
          if (productItems) {
            // Filtrar itens baseado no acesso do usuário
            const accessibleItems = productItems.filter(item => {
              // Pular Chat, Agenda e Contatos (já adicionados acima para admin/gerente/agente)
              if (item.href === '/chat' || item.href === '/agenda' || item.href === '/contacts') {
                return false
              }
              
              if (!item.requiredProduct) {
                return true
              }
              
              // Para Contatos, usar canAccessContacts (verifica role OU flow)
              if (item.href === '/contacts') {
                const access = canAccessContacts()
                return access.canAccess
              }
              
              const access = hasProductAccess(item.requiredProduct)
              return access.canAccess
            })
            items.push(...accessibleItems)
          }
        })
      }
      
      return items
    }
    
    // Para outros usuários, usar lógica normal baseada em produtos
    const items = [...baseNavigation]
    
    // Adicionar itens de menu dos produtos ativos, mas filtrar por acesso
    (activeProductSlugs || []).forEach((productSlug) => {
      const productItems = productMenuItems[productSlug as keyof typeof productMenuItems]
      if (productItems) {
        // Filtrar itens baseado no acesso do usuário
        const accessibleItems = productItems.filter(item => {
          if (!item.requiredProduct) {
            return true
          }
          
          // Para Agenda, usar canAccessAgenda (verifica chat OU workflow)
          if (item.href === '/agenda') {
            const access = canAccessAgenda()
            return access.canAccess
          }
          
          // Para Chat, usar canAccessChat (verifica role OU workflow)
          if (item.href === '/chat') {
            const access = canAccessChat()
            return access.canAccess
          }
          
          // Para Contatos, usar canAccessContacts (verifica role OU flow)
          if (item.href === '/contacts') {
            const access = canAccessContacts()
            return access.canAccess
          }
          
          // Para outros itens, usar verificação normal de produto
          const access = hasProductAccess(item.requiredProduct)
          return access.canAccess
        })
        items.push(...accessibleItems)
      }
    })
    
    return items
  }, [activeProductSlugs, hasProductAccess, canAccessAgenda, canAccessChat, canAccessContacts, isAdmin, isGerente, isAgente, user])

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Mobile sidebar */}
      <div className={cn(
        "fixed inset-0 z-modal lg:hidden",
        sidebarOpen ? "block" : "hidden"
      )}>
        <div className="fixed inset-0 bg-gray-600 bg-opacity-75 dark:bg-gray-900 dark:bg-opacity-75" onClick={() => setSidebarOpen(false)} />
        <div className="relative flex w-full max-w-xs flex-1 flex-col bg-white dark:bg-gray-800">
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
                      ? "bg-brand-100 dark:bg-brand-900 text-brand-700 dark:text-brand-300"
                      : "text-gray-600 dark:text-gray-300 hover:bg-brand-50 dark:hover:bg-gray-700 hover:text-brand-900 dark:hover:text-white"
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
                  <div className="px-2 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">
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
          
          {/* User info - Mobile */}
          <div className="border-t border-gray-200 dark:border-gray-700 p-4">
            <div className="relative" ref={userDropdownRef}>
              {/* User info - Clickable */}
              <button
                onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                className="flex items-center w-full hover:bg-brand-50 dark:hover:bg-gray-700 rounded-md px-2 py-2 transition-colors"
              >
                <Avatar 
                  name={`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username || 'Usuário'} 
                  size="md" 
                />
                <div className="ml-3 flex-1 text-left">
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-200">{`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{user?.tenant?.name}</p>
                </div>
                <ChevronDown className={`h-4 w-4 text-gray-400 dark:text-gray-500 transition-transform ${userDropdownOpen ? 'rotate-180' : ''}`} />
              </button>
              
              {/* User dropdown menu */}
              {userDropdownOpen && (
                <div className="absolute bottom-full left-0 right-0 mb-2 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50">
                  <Link
                    to="/profile"
                    className="flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-brand-50 dark:hover:bg-gray-700 transition-colors"
                    onClick={() => {
                      setUserDropdownOpen(false)
                      setSidebarOpen(false)
                    }}
                  >
                    <User className="h-4 w-4 mr-3 text-gray-400 dark:text-gray-500" />
                    Meu Perfil
                  </Link>
                  
                  <button
                    onClick={() => {
                      setShowPasswordModal(true)
                      setUserDropdownOpen(false)
                      setSidebarOpen(false)
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-brand-50 dark:hover:bg-gray-700 transition-colors"
                  >
                    <Lock className="h-4 w-4 mr-3 text-gray-400 dark:text-gray-500" />
                    Alterar Senha
                  </button>
                  
                  <div className="border-t border-gray-100 dark:border-gray-700 my-1" />
                  
                  <button
                    onClick={() => {
                      setUserDropdownOpen(false)
                      logout()
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                  >
                    <LogOut className="h-4 w-4 mr-3 text-red-500 dark:text-red-400" />
                    <span className="text-gray-700 dark:text-gray-200">Sair</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Desktop sidebar */}
      <div className={cn(
        "hidden md:fixed md:inset-y-0 md:flex md:flex-col transition-all duration-300 z-sidebar",
        sidebarCollapsed ? "md:w-16" : "md:w-64"
      )}>
        <div className="flex flex-col flex-grow bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700">
          <div className="flex h-16 items-center justify-between px-4">
            {!sidebarCollapsed && <Logo size="sm" />}
            <div className="flex items-center gap-2 ml-auto">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              >
                {sidebarCollapsed ? (
                  <ChevronRight className="h-5 w-5" />
                ) : (
                  <ChevronLeft className="h-5 w-5" />
                )}
              </Button>
            </div>
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
                      ? "bg-brand-100 dark:bg-brand-900 text-brand-700 dark:text-brand-300"
                      : "text-gray-600 dark:text-gray-300 hover:bg-brand-50 dark:hover:bg-gray-700 hover:text-brand-900 dark:hover:text-white"
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
                  <div className="px-2 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">
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
          <div className="border-t border-gray-200 dark:border-gray-700 p-4">
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
              <div className="relative" ref={userDropdownRef}>
                {/* User info - Clickable */}
                <button
                  onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                  className="flex items-center w-full hover:bg-brand-50 dark:hover:bg-gray-700 rounded-md px-2 py-2 transition-colors"
                >
                  <Avatar 
                    name={`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username || 'Usuário'} 
                    size="md" 
                  />
                  <div className="ml-3 flex-1 text-left">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200">{`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{user?.tenant?.name}</p>
                  </div>
                  <ChevronDown className={`h-4 w-4 text-gray-400 dark:text-gray-500 transition-transform ${userDropdownOpen ? 'rotate-180' : ''}`} />
                </button>
                
                {/* User dropdown menu */}
                {userDropdownOpen && (
                  <div className="absolute bottom-full left-0 right-0 mb-2 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50">
                    <Link
                      to="/profile"
                      className="flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-brand-50 dark:hover:bg-gray-700 transition-colors"
                      onClick={() => setUserDropdownOpen(false)}
                    >
                      <User className="h-4 w-4 mr-3 text-gray-400 dark:text-gray-500" />
                      Meu Perfil
                    </Link>
                    
                    <button
                      onClick={() => {
                        setShowPasswordModal(true)
                        setUserDropdownOpen(false)
                      }}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-brand-50 dark:hover:bg-gray-700 transition-colors"
                    >
                      <Lock className="h-4 w-4 mr-3 text-gray-400 dark:text-gray-500" />
                      Alterar Senha
                    </button>
                    
                    <div className="border-t border-gray-100 dark:border-gray-700 my-1" />
                    
                    <button
                      onClick={() => {
                        setUserDropdownOpen(false)
                        logout()
                      }}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    >
                      <LogOut className="h-4 w-4 mr-3 text-red-500 dark:text-red-400" />
                      <span className="text-gray-700 dark:text-gray-200">Sair</span>
                    </button>
                  </div>
                )}
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
        {/* Mobile menu button */}
        <div className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 shadow-sm sm:gap-x-6 sm:px-4 md:px-6 lg:px-8 md:hidden">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5 sm:h-6 sm:w-6" />
          </Button>
        </div>

        {/* Page content */}
        {location.pathname === '/chat' ? (
          <main className="p-0 h-[calc(100vh-64px)] md:h-screen overflow-hidden">
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
      
      {/* Change Password Modal */}
      <ChangePasswordModal
        isOpen={showPasswordModal}
        onClose={() => setShowPasswordModal(false)}
      />
    </div>
  )
}
