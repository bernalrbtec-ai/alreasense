import React from 'react'
import { Navigate } from 'react-router-dom'
import { useUserAccess } from '../hooks/useUserAccess'
import { showErrorToast } from '../lib/toastHelper'

interface ProtectedChatRouteProps {
  children: React.ReactNode
  fallbackPath?: string
}

/**
 * Componente que protege a rota do chat.
 * Permite acesso se:
 * - Usuário tem acesso ao chat (admin, gerente ou agente) OU
 * - Tenant tem produto workflow ativo
 */
export const ProtectedChatRoute: React.FC<ProtectedChatRouteProps> = ({
  children,
  fallbackPath = '/dashboard'
}) => {
  const { canAccessChat, loading } = useUserAccess()

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-500"></div>
      </div>
    )
  }

  const access = canAccessChat()
  
  // ✅ DEBUG: Log para entender o problema
  console.log('🔍 [ProtectedChatRoute] Verificando acesso ao chat:', {
    canAccess: access.canAccess,
    loading,
    user: typeof window !== 'undefined' ? JSON.parse(localStorage.getItem('auth-storage') || '{}')?.state?.user : null
  })
  
  if (!access.canAccess) {
    console.error('❌ [ProtectedChatRoute] Acesso negado ao chat:', access)
    showErrorToast('Acesso negado: Você não tem acesso ao chat. É necessário ter acesso ao chat ou ao produto workflow.')
    return <Navigate to={fallbackPath} replace />
  }

  return <>{children}</>
}

