import React from 'react'
import { Navigate } from 'react-router-dom'
import { useUserAccess } from '../hooks/useUserAccess'
import { showErrorToast } from '../lib/toastHelper'

interface ProtectedAgendaRouteProps {
  children: React.ReactNode
  fallbackPath?: string
}

/**
 * Componente que protege a rota da agenda.
 * Permite acesso se:
 * - Usuário tem acesso ao chat (admin, gerente ou agente) OU
 * - Tenant tem produto workflow ativo
 */
export const ProtectedAgendaRoute: React.FC<ProtectedAgendaRouteProps> = ({
  children,
  fallbackPath = '/dashboard'
}) => {
  const { canAccessAgenda, loading } = useUserAccess()

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-500"></div>
      </div>
    )
  }

  const access = canAccessAgenda()
  
  if (!access.canAccess) {
    showErrorToast('Acesso negado: Você não tem acesso à agenda. É necessário ter acesso ao chat ou ao produto workflow.')
    return <Navigate to={fallbackPath} replace />
  }

  return <>{children}</>
}

