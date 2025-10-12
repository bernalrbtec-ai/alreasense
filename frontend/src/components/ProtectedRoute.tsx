import React from 'react'
import { Navigate } from 'react-router-dom'
import { useUserAccess } from '../hooks/useUserAccess'
import { showErrorToast } from '../lib/toastHelper'

interface ProtectedRouteProps {
  children: React.ReactNode
  requiredProduct: string
  fallbackPath?: string
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredProduct,
  fallbackPath = '/dashboard'
}) => {
  const { hasProductAccess, loading } = useUserAccess()

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-500"></div>
      </div>
    )
  }

  const access = hasProductAccess(requiredProduct)
  
  if (!access.canAccess) {
    showErrorToast(`Acesso negado: Você não tem acesso ao produto ${requiredProduct}`)
    return <Navigate to={fallbackPath} replace />
  }

  return <>{children}</>
}

