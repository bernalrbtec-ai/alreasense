import { ReactNode } from 'react';
import { usePermissions } from '../hooks/usePermissions';
import { AlertCircle, Lock } from 'lucide-react';
import { Card } from './ui/Card';

interface PermissionGuardProps {
  children: ReactNode;
  require?: 'admin' | 'gerente' | 'agente' | 'admin_or_gerente';
  permission?: keyof ReturnType<typeof usePermissions>;
  fallback?: ReactNode;
  hideContent?: boolean;
}

/**
 * Componente para proteger conteúdo baseado em permissões.
 * 
 * Uso:
 * <PermissionGuard require="admin">
 *   <AdminOnlyContent />
 * </PermissionGuard>
 * 
 * <PermissionGuard permission="can_manage_users">
 *   <UserManagement />
 * </PermissionGuard>
 */
export function PermissionGuard({
  children,
  require,
  permission,
  fallback,
  hideContent = false,
}: PermissionGuardProps) {
  const perms = usePermissions();

  // Verificar role
  let hasAccess = true;

  if (require) {
    switch (require) {
      case 'admin':
        hasAccess = perms.isAdmin;
        break;
      case 'gerente':
        hasAccess = perms.isGerente;
        break;
      case 'agente':
        hasAccess = perms.isAgente;
        break;
      case 'admin_or_gerente':
        hasAccess = perms.isAdmin || perms.isGerente;
        break;
    }
  }

  // Verificar permissão específica
  if (permission && perms[permission] !== undefined) {
    hasAccess = hasAccess && !!perms[permission];
  }

  // Se tem acesso, mostra o conteúdo
  if (hasAccess) {
    return <>{children}</>;
  }

  // Se não tem acesso e hideContent está ativo, não mostra nada
  if (hideContent) {
    return null;
  }

  // Se tem fallback customizado, usa ele
  if (fallback) {
    return <>{fallback}</>;
  }

  // Fallback padrão
  const getMessage = () => {
    if (require === 'admin') {
      return 'Apenas administradores têm acesso a este recurso.';
    }
    if (require === 'admin_or_gerente') {
      return 'Apenas administradores e gerentes têm acesso a este recurso.';
    }
    if (permission) {
      return perms.getNoPermissionMessage('acessar este recurso');
    }
    return 'Você não tem permissão para acessar este recurso.';
  };

  return (
    <Card className="p-6">
      <div className="text-center">
        <Lock className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Acesso Restrito
        </h3>
        <p className="text-gray-600 mb-4">{getMessage()}</p>
        <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
          <AlertCircle className="h-4 w-4" />
          <span>
            Entre em contato com um administrador para solicitar acesso.
          </span>
        </div>
      </div>
    </Card>
  );
}

/**
 * Hook para verificar permissão de forma imperativa.
 * 
 * Uso:
 * const { checkPermission } = usePermissionCheck();
 * if (checkPermission('can_manage_users')) {
 *   // fazer algo
 * }
 */
export function usePermissionCheck() {
  const perms = usePermissions();

  const checkPermission = (permission: keyof ReturnType<typeof usePermissions>) => {
    return !!perms[permission];
  };

  const checkRole = (role: 'admin' | 'gerente' | 'agente') => {
    switch (role) {
      case 'admin':
        return perms.isAdmin;
      case 'gerente':
        return perms.isGerente;
      case 'agente':
        return perms.isAgente;
      default:
        return false;
    }
  };

  return {
    checkPermission,
    checkRole,
    ...perms,
  };
}

