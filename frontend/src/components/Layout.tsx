import { useState, useMemo } from 'react'
import { Link, useLocation } from 'react-router-dom'
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
  Bell,
  ChevronLeft,
  ChevronRight
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useTenantProducts } from '../hooks/useTenantProducts'
import { Button } from './ui/Button'
import Logo from './ui/Logo'
import Avatar from './ui/Avatar'
import UserDropdown from './UserDropdown'
import { cn } from '@/lib/utils'

// Mapeamento de produtos para itens do menu
const productMenuItems = {
  flow: [
    { name: 'Mensagens', href: '/messages', icon: MessageSquare },
    { name: 'Conexões', href: '/connections', icon: Wifi },
  ],
  sense: [
    { name: 'Experimentos', href: '/experiments', icon: FlaskConical },
  ],
}

const baseNavigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Billing', href: '/billing', icon: CreditCard },
]

const adminNavigation = [
  { name: 'Clientes', href: '/admin/tenants', icon: Users },
  { name: 'Planos', href: '/admin/plans', icon: Package },
  { name: 'Status do Sistema', href: '/admin/system', icon: Activity },
  { name: 'Servidor de Instância', href: '/admin/evolution', icon: Server },
  { name: 'Notificações', href: '/admin/notifications', icon: Bell },
]

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const { activeProductSlugs, loading: productsLoading } = useTenantProducts()
  
  const isSuperAdmin = user?.is_superuser || user?.is_staff
  
  // Gerar navegação dinâmica baseada nos produtos ativos
  const navigation = useMemo(() => {
    const items = [...baseNavigation]
    
    // Adicionar itens de menu dos produtos ativos
    activeProductSlugs.forEach((productSlug) => {
      const productItems = productMenuItems[productSlug as keyof typeof productMenuItems]
      if (productItems) {
        items.push(...productItems)
      }
    })
    
    return items
  }, [activeProductSlugs])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar */}
      <div className={cn(
        "fixed inset-0 z-50 lg:hidden",
        sidebarOpen ? "block" : "hidden"
      )}>
        <div className="fixed inset-0 bg-gray-600 bg-opacity-75" onClick={() => setSidebarOpen(false)} />
        <div className="fixed inset-y-0 left-0 flex w-64 flex-col bg-white">
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
            
            {/* Admin Section */}
            {isSuperAdmin && (
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
        "hidden lg:fixed lg:inset-y-0 lg:flex lg:flex-col transition-all duration-300",
        sidebarCollapsed ? "lg:w-16" : "lg:w-64"
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
            
            {/* Admin Section */}
            {isSuperAdmin && !sidebarCollapsed && (
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
        sidebarCollapsed ? "lg:pl-16" : "lg:pl-64"
      )}>
        {/* Top bar */}
        <div className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 bg-white px-4 shadow-sm sm:gap-x-6 sm:px-6 lg:px-8">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-6 w-6" />
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
        <main className="py-6">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
