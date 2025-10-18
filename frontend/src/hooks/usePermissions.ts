import { useAuthStore } from '../stores/authStore'

/**
 * Hook para verificar permissões do usuário baseado no role e departamentos.
 * 
 * Roles:
 * - admin: Acesso total ao tenant
 * - gerente: Métricas e chat dos seus departamentos
 * - agente: Apenas chat dos seus departamentos
 */
export const usePermissions = () => {
  const { user } = useAuthStore()

  // Permissões diretas do backend (sempre usar essas quando disponíveis)
  const permissions = user?.permissions || {
    can_access_all_departments: false,
    can_view_metrics: false,
    can_access_chat: false,
    can_manage_users: false,
    can_manage_departments: false,
    can_manage_campaigns: false,
    can_view_all_contacts: false,
  }

  // Helpers baseados no role (fallback se permissions não estiver disponível)
  const isAdmin = user?.is_admin || user?.role === 'admin' || user?.is_superuser
  const isGerente = user?.is_gerente || user?.role === 'gerente'
  const isAgente = user?.is_agente || user?.role === 'agente'

  // Verificar se usuário tem departamentos
  const hasDepartments = user?.department_ids && user.department_ids.length > 0

  return {
    // Informações do usuário
    user,
    isAdmin,
    isGerente,
    isAgente,
    hasDepartments,
    departmentIds: user?.department_ids || [],
    departmentNames: user?.department_names || [],

    // Permissões principais
    ...permissions,

    // Helpers adicionais
    canAccessDashboard: isAdmin || isGerente,
    canAccessSettings: isAdmin,
    canViewReports: isAdmin || isGerente,
    canExportData: isAdmin,

    // Verificar acesso a departamento específico
    canAccessDepartment: (departmentId: string) => {
      if (isAdmin) return true
      if (!user?.department_ids) return false
      return user.department_ids.includes(departmentId)
    },

    // Verificar se precisa filtrar por departamento
    needsDepartmentFilter: !isAdmin && (isGerente || isAgente),

    // Mensagens de erro
    getNoPermissionMessage: (action: string) => {
      if (isAgente) {
        return `Agentes não têm permissão para ${action}. Apenas administradores e gerentes.`
      }
      if (isGerente) {
        return `Gerentes não têm permissão para ${action}. Apenas administradores.`
      }
      return `Você não tem permissão para ${action}.`
    },
  }
}

