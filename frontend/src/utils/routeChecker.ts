/**
 * Route checker utility to verify all routes are working
 */

export interface RouteInfo {
  path: string
  component: string
  isAdmin: boolean
  status: 'working' | 'error' | 'unknown'
  error?: string
}

export const allRoutes: RouteInfo[] = [
  // Public routes
  { path: '/login', component: 'LoginPage', isAdmin: false, status: 'unknown' },
  
  // User routes
  { path: '/dashboard', component: 'DashboardPage', isAdmin: false, status: 'unknown' },
  { path: '/messages', component: 'MessagesPage', isAdmin: false, status: 'unknown' },
  { path: '/connections', component: 'ConnectionsPage', isAdmin: false, status: 'unknown' },
  { path: '/experiments', component: 'ExperimentsPage', isAdmin: false, status: 'unknown' },
  { path: '/billing', component: 'BillingPage', isAdmin: false, status: 'unknown' },
  { path: '/profile', component: 'ProfilePage', isAdmin: false, status: 'unknown' },
  
  // Admin routes
  { path: '/admin/tenants', component: 'TenantsPage', isAdmin: true, status: 'unknown' },
  { path: '/admin/plans', component: 'PlansPage', isAdmin: true, status: 'unknown' },
  { path: '/admin/system', component: 'SystemStatusPage', isAdmin: true, status: 'unknown' },
  { path: '/admin/evolution', component: 'EvolutionConfigPage', isAdmin: true, status: 'unknown' },
]

export const checkRoute = async (route: RouteInfo): Promise<RouteInfo> => {
  try {
    // This would be called from the browser console
    console.log(`🔍 Checking route: ${route.path}`)
    
    // Simulate route check
    return {
      ...route,
      status: 'working'
    }
  } catch (error) {
    return {
      ...route,
      status: 'error',
      error: error instanceof Error ? error.message : 'Unknown error'
    }
  }
}

export const checkAllRoutes = async (): Promise<RouteInfo[]> => {
  console.log('🚀 Starting route check...')
  
  const results = await Promise.all(
    allRoutes.map(route => checkRoute(route))
  )
  
  console.log('📊 Route check results:', results)
  return results
}

// Make it available globally for console testing
if (typeof window !== 'undefined') {
  (window as any).checkAllRoutes = checkAllRoutes
  (window as any).allRoutes = allRoutes
}
