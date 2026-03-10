import { useAuthStore } from '../stores/authStore'
import { useTenantProducts } from './useTenantProducts'
import { usePermissions } from './usePermissions'

export interface ProductAccess {
  canAccess: boolean
  isActive: boolean
  limit?: number
  currentUsage?: number
}

export const useUserAccess = () => {
  const { user } = useAuthStore()
  const { products, loading } = useTenantProducts()
  const { can_access_chat, isAdmin, isGerente, isAgente } = usePermissions()

  // ✅ CORREÇÃO CRÍTICA: Garantir que products está sempre definido antes de usar
  const safeProducts = Array.isArray(products) ? products : []

  const hasProductAccess = (productSlug: string): ProductAccess => {
    // Super admin tem acesso a tudo
    if (user?.is_superuser || user?.is_staff) {
      return { canAccess: true, isActive: true }
    }

    // Se não tem tenant_id ou produtos carregando, não tem acesso
    if (!user?.tenant_id || loading) {
      return { canAccess: false, isActive: false }
    }

    // ✅ CORREÇÃO: Usar safeProducts ao invés de products diretamente
    // Buscar o produto nas TenantProducts
    const tenantProduct = safeProducts.find(tp => tp && tp.product && tp.product.slug === productSlug)
    
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
    // Produto Flow = apenas campanhas.
    return hasProductAccess('flow')
  }

  const canAccessInstances = (): ProductAccess => {
    // Instâncias WhatsApp: apenas produto chat (flow = apenas campanhas)
    return hasProductAccess('chat')
  }

  const canAccessSense = (): ProductAccess => {
    return hasProductAccess('sense')
  }

  const canAccessContacts = (): ProductAccess => {
    // Contatos: role OU produto chat (flow = apenas campanhas)
    const userRole = user?.role
    const userIsAdmin = user?.is_admin === true || userRole === 'admin' || user?.is_superuser === true
    const userIsGerente = user?.is_gerente === true || userRole === 'gerente'
    const userIsAgente = user?.is_agente === true || userRole === 'agente'
    if (userIsAdmin || userIsGerente || userIsAgente) {
      return { canAccess: true, isActive: true }
    }
    return hasProductAccess('chat')
  }

  const canAccessApiPublic = (): ProductAccess => {
    return hasProductAccess('api_public')
  }

  const canAccessCampaigns = (): ProductAccess => {
    // Campanhas: apenas produto Flow
    return hasProductAccess('flow')
  }

  const canAccessWorkflow = (): ProductAccess => {
    // Workflow inclui Chat + Agenda/Tarefas
    return hasProductAccess('workflow')
  }

  const canAccessChat = (): ProductAccess => {
    // Chat: role (admin/gerente/agente) OU produto workflow OU produto chat (ALREA Chat unifica chat, agenda, contatos)
    const userRole = user?.role
    const userIsAdmin = user?.is_admin === true || userRole === 'admin' || user?.is_superuser === true
    const userIsGerente = user?.is_gerente === true || userRole === 'gerente'
    const userIsAgente = user?.is_agente === true || userRole === 'agente'
    if (userIsAdmin || userIsGerente || userIsAgente) {
      return { canAccess: true, isActive: true }
    }
    const chatAccess = hasProductAccess('chat')
    if (chatAccess.canAccess) return chatAccess
    return canAccessWorkflow()
  }

  const canAccessAgenda = (): ProductAccess => {
    // Agenda: role (admin/gerente/agente) OU produto workflow OU produto chat (ALREA Chat unifica chat, agenda, contatos)
    const userRole = user?.role
    const hasChatAccess = can_access_chat || isAdmin || isGerente || isAgente ||
                          userRole === 'admin' || userRole === 'gerente' || userRole === 'agente'
    if (hasChatAccess) {
      return { canAccess: true, isActive: true }
    }
    const chatAccess = hasProductAccess('chat')
    if (chatAccess.canAccess) return chatAccess
    return canAccessWorkflow()
  }

  return {
    hasProductAccess,
    canAccessFlow,
    canAccessInstances,
    canAccessSense,
    canAccessContacts,
    canAccessApiPublic,
    canAccessCampaigns,
    canAccessWorkflow,
    canAccessChat,
    canAccessAgenda,
    loading
  }
}
