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

  const hasProductAccess = (productSlug: string): ProductAccess => {
    // Super admin tem acesso a tudo
    if (user?.is_superuser || user?.is_staff) {
      return { canAccess: true, isActive: true }
    }

    // Se não tem tenant_id ou produtos carregando, não tem acesso
    if (!user?.tenant_id || loading) {
      return { canAccess: false, isActive: false }
    }

    // Buscar o produto nas TenantProducts
    const tenantProduct = Array.isArray(products) 
      ? products.find(tp => tp && tp.product && tp.product.slug === productSlug)
      : null
    
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
    // Contatos podem ser acessados se:
    // 1. Usuário tem acesso ao chat (admin, gerente ou agente) OU
    // 2. Tenant tem produto flow ativo
    
    // Verificar acesso ao chat primeiro - verificar role diretamente também
    const userRole = user?.role
    const userIsAdmin = user?.is_admin === true || userRole === 'admin' || user?.is_superuser === true
    const userIsGerente = user?.is_gerente === true || userRole === 'gerente'
    const userIsAgente = user?.is_agente === true || userRole === 'agente'
    
    // Admin/Gerente/Agente sempre têm acesso (contatos fazem parte do chat/agenda)
    if (userIsAdmin || userIsGerente || userIsAgente) {
      return { canAccess: true, isActive: true }
    }
    
    // Se não tem acesso ao chat, verificar produto flow
    return canAccessFlow()
  }

  const canAccessApiPublic = (): ProductAccess => {
    return hasProductAccess('api_public')
  }

  const canAccessCampaigns = (): ProductAccess => {
    // Campanhas fazem parte do produto Flow
    return canAccessFlow()
  }

  const canAccessWorkflow = (): ProductAccess => {
    // Workflow inclui Chat + Agenda/Tarefas
    return hasProductAccess('workflow')
  }

  const canAccessChat = (): ProductAccess => {
    // Chat pode ser acessado se:
    // 1. Usuário tem acesso ao chat (admin, gerente ou agente) OU
    // 2. Tenant tem produto workflow ativo
    
    // ✅ FIX CRÍTICO: Admin sempre tem acesso, verificar PRIMEIRO
    const userRole = user?.role
    const userIsAdmin = user?.is_admin === true || userRole === 'admin' || user?.is_superuser === true
    const userIsGerente = user?.is_gerente === true || userRole === 'gerente'
    const userIsAgente = user?.is_agente === true || userRole === 'agente'
    
    // ✅ DEBUG: Log para entender o problema
    console.log('🔍 [canAccessChat] Verificando acesso:', {
      userRole,
      userIsAdmin,
      userIsGerente,
      userIsAgente,
      user_is_admin: user?.is_admin,
      user_is_superuser: user?.is_superuser,
      can_access_chat,
      isAdmin,
      isGerente,
      isAgente,
      user: user ? { id: user.id, email: user.email, role: user.role, is_admin: user.is_admin, is_superuser: user.is_superuser } : null
    })
    
    // ✅ CRÍTICO: Admin sempre tem acesso - verificar ANTES de tudo
    if (userIsAdmin) {
      console.log('✅ [canAccessChat] Admin detectado - acesso garantido')
      return { canAccess: true, isActive: true }
    }
    
    // Verificar outros roles
    const hasChatAccess = userIsGerente || userIsAgente || 
                          can_access_chat || isGerente || isAgente
    
    if (hasChatAccess) {
      console.log('✅ [canAccessChat] Acesso permitido via role/permissão')
      return { canAccess: true, isActive: true }
    }
    
    // Se não tem acesso ao chat, verificar produto workflow
    const workflowAccess = canAccessWorkflow()
    console.log('🔍 [canAccessChat] Verificando produto workflow:', workflowAccess)
    return workflowAccess
  }

  const canAccessAgenda = (): ProductAccess => {
    // Agenda pode ser acessada se:
    // 1. Usuário tem acesso ao chat (admin, gerente ou agente) OU
    // 2. Tenant tem produto workflow ativo
    
    // Verificar acesso ao chat primeiro - verificar role diretamente também
    const userRole = user?.role
    const hasChatAccess = can_access_chat || isAdmin || isGerente || isAgente || 
                          userRole === 'admin' || userRole === 'gerente' || userRole === 'agente'
    
    if (hasChatAccess) {
      return { canAccess: true, isActive: true }
    }
    
    // Se não tem acesso ao chat, verificar produto workflow
    return canAccessWorkflow()
  }

  return {
    hasProductAccess,
    canAccessFlow,
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
