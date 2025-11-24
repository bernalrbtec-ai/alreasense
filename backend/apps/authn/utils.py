"""
Funções auxiliares para gerenciamento de departamentos e permissões.

⚠️ IMPORTANTE: Estas funções são reutilizáveis em outros módulos do sistema
(relatórios, dashboards, permissões, etc.). Mantenha-as genéricas e bem documentadas.
"""

from django.db.models import Q
from django.utils import timezone
import uuid as uuid_module
from apps.authn.models import Department, User
from apps.contacts.models import Task


def is_department_manager(user, department):
    """
    Verifica se o usuário é gestor do departamento.
    
    REGRAS:
    - Admin sempre é gestor de todos os departamentos
    - Gerente é gestor apenas dos departamentos onde está vinculado
    - Agente nunca é gestor
    
    Args:
        user: Instância de User
        department: Instância de Department, ID (int/str) ou UUID
    
    Returns:
        bool: True se o usuário é gestor do departamento
    
    Raises:
        Department.DoesNotExist: Se department for ID e não existir
    """
    # Validar entrada
    if not user or not user.is_authenticated:
        return False
    
    # Admin sempre pode gerenciar qualquer departamento do tenant
    if user.role == 'admin':
        # Verificar se o departamento pertence ao mesmo tenant
        if isinstance(department, (int, str, uuid_module.UUID)):
            try:
                dept = Department.objects.get(id=department, tenant=user.tenant)
                return True
            except Department.DoesNotExist:
                return False
        return department.tenant == user.tenant
    
    # Gerente pode gerenciar apenas departamentos onde está vinculado
    if user.role == 'gerente':
        if isinstance(department, (int, str, uuid_module.UUID)):
            try:
                dept = Department.objects.get(id=department, tenant=user.tenant)
            except Department.DoesNotExist:
                return False
        else:
            dept = department
        
        # Verificar se o usuário está no departamento E se o departamento pertence ao tenant
        return dept.tenant == user.tenant and user.departments.filter(id=dept.id).exists()
    
    # Agente nunca é gestor
    return False


def get_user_managed_departments(user):
    """
    Retorna todos os departamentos que o usuário gerencia.
    
    REGRAS:
    - Admin: Todos os departamentos do tenant
    - Gerente: Apenas departamentos onde está vinculado
    - Agente: Nenhum
    
    Args:
        user: Instância de User
    
    Returns:
        QuerySet: Departamentos gerenciados pelo usuário
    """
    if not user or not user.is_authenticated:
        return Department.objects.none()
    
    # Admin gerencia todos os departamentos do tenant
    if user.role == 'admin':
        return Department.objects.filter(tenant=user.tenant, is_active=True)
    
    # Gerente gerencia apenas departamentos onde está vinculado
    if user.role == 'gerente':
        return user.departments.filter(tenant=user.tenant, is_active=True)
    
    # Agente não gerencia nenhum departamento
    return Department.objects.none()


def can_manage_department_notifications(user, department):
    """
    Verifica se o usuário pode gerenciar notificações do departamento.
    
    Esta função é um wrapper de is_department_manager() para uso específico
    em notificações, mas pode ser reutilizada para outras funcionalidades.
    
    Args:
        user: Instância de User
        department: Instância de Department, ID (int/str) ou UUID
    
    Returns:
        bool: True se o usuário pode gerenciar notificações do departamento
    """
    return is_department_manager(user, department)


def can_manage_department(user, department, action='view'):
    """
    Verifica se o usuário pode realizar uma ação no departamento.
    
    Esta é uma função genérica que pode ser usada em múltiplos contextos:
    - Notificações
    - Relatórios
    - Dashboards
    - Configurações
    - etc.
    
    Args:
        user: Instância de User
        department: Instância de Department, ID (int/str) ou UUID
        action: String indicando a ação ('view', 'edit', 'delete', 'manage')
    
    Returns:
        bool: True se o usuário pode realizar a ação
    """
    if not user or not user.is_authenticated:
        return False
    
    # Admin sempre pode tudo
    if user.role == 'admin':
        return True
    
    # Verificar se é gestor do departamento
    if is_department_manager(user, department):
        # Gerente pode ver e editar, mas não deletar (a menos que seja admin)
        if action in ['view', 'edit', 'manage']:
            return True
        if action == 'delete':
            return user.role == 'admin'
    
    return False


def get_department_tasks(department, filters=None, tenant=None):
    """
    Retorna todas as tarefas do departamento.
    
    REGRAS:
    - Inclui tarefas onde department = X
    - Inclui tarefas onde assigned_to está no departamento X
    - Sempre filtra por tenant (multi-tenancy)
    
    Args:
        department: Instância de Department ou ID
        filters: Dict com filtros adicionais:
            - status: Lista de status ['pending', 'in_progress', etc]
            - priority: Lista de prioridades ['low', 'medium', 'high', 'urgent']
            - overdue_only: bool - apenas tarefas atrasadas
            - assigned_only: bool - apenas tarefas com assigned_to
            - date_range: tuple (start_date, end_date)
        tenant: Instância de Tenant (obrigatório para multi-tenancy)
    
    Returns:
        QuerySet: Tarefas do departamento
    
    Raises:
        ValueError: Se tenant não for fornecido
    """
    if tenant is None:
        if isinstance(department, Department):
            tenant = department.tenant
        else:
            raise ValueError("tenant deve ser fornecido quando department é ID")
    
    # Converter department para instância se necessário
    if isinstance(department, (int, str, uuid_module.UUID)):
        try:
            department = Department.objects.get(id=department, tenant=tenant)
        except Department.DoesNotExist:
            return Task.objects.none()
    
    # Buscar tarefas do departamento
    # Tarefas onde o departamento é o mesmo OU o usuário atribuído está no departamento
    tasks = Task.objects.filter(
        tenant=tenant
    ).filter(
        Q(department=department) |
        Q(assigned_to__departments=department)
    ).distinct()
    
    # Aplicar filtros adicionais
    if filters:
        if filters.get('status'):
            tasks = tasks.filter(status__in=filters['status'])
        
        if filters.get('priority'):
            tasks = tasks.filter(priority__in=filters['priority'])
        
        if filters.get('overdue_only'):
            tasks = tasks.filter(
                due_date__lt=timezone.now(),
                status__in=['pending', 'in_progress']
            )
        
        if filters.get('assigned_only'):
            tasks = tasks.exclude(assigned_to__isnull=True)
        
        if filters.get('date_range'):
            start_date, end_date = filters['date_range']
            tasks = tasks.filter(due_date__date__gte=start_date, due_date__date__lte=end_date)
    
    return tasks.select_related('assigned_to', 'created_by', 'tenant', 'department').prefetch_related('related_contacts')

