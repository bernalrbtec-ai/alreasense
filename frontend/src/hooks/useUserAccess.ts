import { useAuthStore } from '../stores/authStore'
import { useTenantProducts } from './useTenantProducts'

export interface ProductAccess {
  canAccess: boolean
  isActive: boolean
  limit?: number
  currentUsage?: number
}

export const useUserAccess = () => {
  const { user } = useAuthStore()
  const { products, loading } = useTenantProducts()

  const hasProductAccess = (productSlug: string): ProductAccess => {
    // Super admin tem acesso a tudo
    if (user?.role === 'superadmin') {
      return { canAccess: true, isActive: true }
    }

    // Se não tem tenant_id ou produtos carregando, não tem acesso
    if (!user?.tenant_id || loading) {
      return { canAccess: false, isActive: false }
    }

    // Buscar o produto nas TenantProducts
    const tenantProduct = products.find(tp => tp.product.slug === productSlug)
    
    if (!tenantProduct) {
      return { canAccess: false, isActive: false }
    }

    const canAccess = tenantProduct.is_active
    
    return {
      canAccess: canAccess,
      isActive: canAccess,
      limit: undefined, // TODO: implementar limites se necessário
      currentUsage: undefined
    }
  }

  const canAccessFlow = (): ProductAccess => {
    return hasProductAccess('flow')
  }

  const canAccessSense = (): ProductAccess => {
    return hasProductAccess('sense')
  }

  const canAccessContacts = (): ProductAccess => {
    return hasProductAccess('contacts')
  }

  const canAccessApiPublic = (): ProductAccess => {
    return hasProductAccess('api_public')
  }

  const canAccessCampaigns = (): ProductAccess => {
    // Campanhas fazem parte do produto Flow
    return canAccessFlow()
  }

  return {
    hasProductAccess,
    canAccessFlow,
    canAccessSense,
    canAccessContacts,
    canAccessApiPublic,
    canAccessCampaigns,
    loading
  }
}
