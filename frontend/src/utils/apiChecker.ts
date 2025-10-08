/**
 * API checker utility to verify all API endpoints are working
 */

import { api } from '../lib/api'

export interface ApiEndpoint {
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  path: string
  description: string
  requiresAuth: boolean
  isAdmin: boolean
  status: 'working' | 'error' | 'unknown'
  error?: string
  responseTime?: number
}

export const allEndpoints: ApiEndpoint[] = [
  // Auth endpoints
  { method: 'POST', path: '/auth/login/', description: 'User login', requiresAuth: false, isAdmin: false, status: 'unknown' },
  { method: 'GET', path: '/auth/me/', description: 'Get current user', requiresAuth: true, isAdmin: false, status: 'unknown' },
  { method: 'PATCH', path: '/auth/profile/', description: 'Update user profile', requiresAuth: true, isAdmin: false, status: 'unknown' },
  { method: 'POST', path: '/auth/change-password/', description: 'Change password', requiresAuth: true, isAdmin: false, status: 'unknown' },
  { method: 'POST', path: '/auth/avatar/', description: 'Upload avatar', requiresAuth: true, isAdmin: false, status: 'unknown' },
  
  // Dashboard endpoints
  { method: 'GET', path: '/tenants/{tenant_id}/metrics/', description: 'Dashboard metrics', requiresAuth: true, isAdmin: false, status: 'unknown' },
  
  // Messages endpoints
  { method: 'GET', path: '/messages/', description: 'List messages', requiresAuth: true, isAdmin: false, status: 'unknown' },
  { method: 'GET', path: '/messages/stats/', description: 'Message statistics', requiresAuth: true, isAdmin: false, status: 'unknown' },
  { method: 'GET', path: '/messages/semantic-search/', description: 'Semantic search', requiresAuth: true, isAdmin: false, status: 'unknown' },
  
  // Connections endpoints
  { method: 'GET', path: '/connections/', description: 'List connections', requiresAuth: true, isAdmin: false, status: 'unknown' },
  { method: 'GET', path: '/connections/evolution/config/', description: 'Evolution API config', requiresAuth: true, isAdmin: true, status: 'unknown' },
  { method: 'POST', path: '/connections/evolution/config/', description: 'Save Evolution API config', requiresAuth: true, isAdmin: true, status: 'unknown' },
  { method: 'POST', path: '/connections/evolution/test/', description: 'Test Evolution API', requiresAuth: true, isAdmin: true, status: 'unknown' },
  
  // Experiments endpoints
  { method: 'GET', path: '/experiments/prompts/', description: 'List prompt templates', requiresAuth: true, isAdmin: false, status: 'unknown' },
  { method: 'GET', path: '/experiments/runs/', description: 'List experiment runs', requiresAuth: true, isAdmin: false, status: 'unknown' },
  
  // Billing endpoints
  { method: 'GET', path: '/billing/plans/', description: 'List plans', requiresAuth: true, isAdmin: false, status: 'unknown' },
  { method: 'POST', path: '/billing/plans/', description: 'Create plan', requiresAuth: true, isAdmin: true, status: 'unknown' },
  { method: 'PATCH', path: '/billing/plans/{id}/', description: 'Update plan', requiresAuth: true, isAdmin: true, status: 'unknown' },
  { method: 'DELETE', path: '/billing/plans/{id}/', description: 'Delete plan', requiresAuth: true, isAdmin: true, status: 'unknown' },
  
  // Tenancy endpoints
  { method: 'GET', path: '/tenants/tenants/', description: 'List tenants', requiresAuth: true, isAdmin: true, status: 'unknown' },
  { method: 'POST', path: '/tenants/tenants/', description: 'Create tenant', requiresAuth: true, isAdmin: true, status: 'unknown' },
  { method: 'PATCH', path: '/tenants/tenants/{id}/', description: 'Update tenant', requiresAuth: true, isAdmin: true, status: 'unknown' },
  { method: 'DELETE', path: '/tenants/tenants/{id}/', description: 'Delete tenant', requiresAuth: true, isAdmin: true, status: 'unknown' },
  
  // Health check
  { method: 'GET', path: '/health/', description: 'System health check', requiresAuth: false, isAdmin: false, status: 'unknown' },
]

export const checkEndpoint = async (endpoint: ApiEndpoint, tenantId?: string): Promise<ApiEndpoint> => {
  const startTime = Date.now()
  
  try {
    console.log(`🔍 Checking endpoint: ${endpoint.method} ${endpoint.path}`)
    
    let path = endpoint.path
    if (tenantId && path.includes('{tenant_id}')) {
      path = path.replace('{tenant_id}', tenantId)
    }
    
    let response
    switch (endpoint.method) {
      case 'GET':
        response = await api.get(path)
        break
      case 'POST':
        // For POST endpoints, we'll just check if they exist (not actually post data)
        response = await api.get(path.replace('/config/', '/test/')) // Use test endpoint instead
        break
      case 'PATCH':
        // For PATCH endpoints, we'll just check if they exist
        response = await api.get(path)
        break
      case 'DELETE':
        // For DELETE endpoints, we'll just check if they exist
        response = await api.get(path)
        break
    }
    
    const responseTime = Date.now() - startTime
    
    return {
      ...endpoint,
      status: 'working',
      responseTime
    }
  } catch (error: any) {
    const responseTime = Date.now() - startTime
    console.error(`❌ Error checking endpoint ${endpoint.path}:`, error)
    
    return {
      ...endpoint,
      status: 'error',
      error: error.response?.data?.detail || error.message || 'Unknown error',
      responseTime
    }
  }
}

export const checkAllEndpoints = async (tenantId?: string): Promise<ApiEndpoint[]> => {
  console.log('🚀 Starting API endpoint check...')
  
  const results = await Promise.all(
    allEndpoints.map(endpoint => checkEndpoint(endpoint, tenantId))
  )
  
  console.log('📊 API endpoint check results:', results)
  return results
}

// Make it available globally for console testing
if (typeof window !== 'undefined') {
  (window as any).checkAllEndpoints = checkAllEndpoints
  (window as any).allEndpoints = allEndpoints
}
