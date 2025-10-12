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
    console.log(`🔍 useUserAccess - Verificando acesso para ${productSlug}`)
    console.log(`   User:`, user)
    console.log(`   Products:`, products)
    console.log(`   Loading:`, loading)
    
    // Super admin tem acesso a tudo
    if (user?.role === 'superadmin') {
      console.log(`   ✅ Superadmin - acesso total`)
      return { canAccess: true, isActive: true }
    }

    // Se não tem tenant ou produtos carregando, não tem acesso
    if (!user?.tenant || loading) {
      console.log(`   ❌ Sem tenant ou carregando - sem acesso`)
      return { canAccess: false, isActive: false }
    }

    // Buscar o produto nas TenantProducts
    const tenantProduct = products.find(tp => tp.product.slug === productSlug)
    console.log(`   TenantProduct encontrado:`, tenantProduct)
    
    if (!tenantProduct) {
      console.log(`   ❌ Produto ${productSlug} não encontrado`)
      return { canAccess: false, isActive: false }
    }

    const canAccess = tenantProduct.is_active
    console.log(`   ✅ Produto ${productSlug}: canAccess=${canAccess}`)
    
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
