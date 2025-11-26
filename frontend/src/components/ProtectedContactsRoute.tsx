import React from 'react'
import { Navigate } from 'react-router-dom'
import { useUserAccess } from '../hooks/useUserAccess'
import { showErrorToast } from '../lib/toastHelper'

interface ProtectedContactsRouteProps {
  children: React.ReactNode
  fallbackPath?: string
}

/**
 * Componente que protege a rota de contatos.
 * Permite acesso se:
 * - Usuário tem acesso ao chat (admin, gerente ou agente) OU
 * - Tenant tem produto flow ativo
 */
export const ProtectedContactsRoute: React.FC<ProtectedContactsRouteProps> = ({
  children,
  fallbackPath = '/dashboard'
}) => {
  const { canAccessContacts, loading } = useUserAccess()

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-500"></div>
      </div>
    )
  }

  const access = canAccessContacts()

  if (!access.canAccess) {
    showErrorToast('Acesso negado: Você não tem acesso aos contatos. É necessário ter acesso ao chat ou ao produto flow.')
    return <Navigate to={fallbackPath} replace />
  }

  return <>{children}</>
}

