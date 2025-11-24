"""
Permissões para o sistema de notificações personalizadas.
"""

from rest_framework import permissions


class CanManageDepartmentNotifications(permissions.BasePermission):
    """
    Permissão para gerenciar notificações de departamento.
    Apenas gestores do departamento podem configurar.
    """
    
    def has_permission(self, request, view):
        # Apenas autenticados
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin sempre pode
        if request.user.role == 'admin':
            return True
        
        # Para métodos que requerem department_id
        department_id = request.data.get('department') or request.query_params.get('department')
        if department_id:
            from apps.authn.utils import can_manage_department_notifications
            from apps.authn.models import Department
            try:
                department = Department.objects.get(id=department_id, tenant=request.user.tenant)
                return can_manage_department_notifications(request.user, department)
            except Department.DoesNotExist:
                return False
        
        # Para métodos que usam department no path (ex: /departments/{id}/notifications/)
        if hasattr(view, 'get_department'):
            department = view.get_department()
            if department:
                from apps.authn.utils import can_manage_department_notifications
                return can_manage_department_notifications(request.user, department)
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica permissão para um objeto específico (DepartmentNotificationPreferences).
        """
        # Admin sempre pode
        if request.user.role == 'admin':
            return True
        
        # Verificar se o usuário é gestor do departamento
        from apps.authn.utils import can_manage_department_notifications
        return can_manage_department_notifications(request.user, obj.department)

