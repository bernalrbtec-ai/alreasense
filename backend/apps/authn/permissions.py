"""
Permissions para controle de acesso baseado em roles e departamentos.
"""
from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Apenas administradores do tenant têm acesso.
    """
    message = 'Apenas administradores têm acesso a este recurso.'

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin


class IsGerenteOrAdmin(permissions.BasePermission):
    """
    Gerentes e administradores têm acesso.
    """
    message = 'Apenas gerentes e administradores têm acesso a este recurso.'

    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_admin or request.user.is_gerente)
        )


class CanAccessDepartment(permissions.BasePermission):
    """
    Verifica se o usuário tem acesso ao departamento específico.
    Admin: acesso total
    Gerente/Agente: apenas aos seus departamentos
    """
    message = 'Você não tem permissão para acessar este departamento.'

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Admin tem acesso total
        if user.is_admin:
            return True
        
        # Extrair department do objeto
        department = None
        if hasattr(obj, 'department'):
            department = obj.department
        elif hasattr(obj, 'departments'):
            # Se for ManyToMany, verifica se user tem acesso a algum
            return obj.departments.filter(users=user).exists()
        
        # Verifica se user pertence ao departamento
        if department:
            return user.departments.filter(id=department.id).exists()
        
        return False


class CanViewMetrics(permissions.BasePermission):
    """
    Verifica se o usuário pode visualizar métricas.
    Admin: todas as métricas
    Gerente: métricas dos seus departamentos
    Agente: sem acesso
    """
    message = 'Você não tem permissão para visualizar métricas.'

    def has_permission(self, request, view):
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Admin e Gerente podem ver métricas
        return user.is_admin or user.is_gerente

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Admin tem acesso total
        if user.is_admin:
            return True
        
        # Gerente só pode ver métricas dos seus departamentos
        if user.is_gerente:
            department = getattr(obj, 'department', None)
            if department:
                return user.departments.filter(id=department.id).exists()
        
        return False


class CanAccessChat(permissions.BasePermission):
    """
    Verifica se o usuário pode acessar chat.
    Admin: todos os chats
    Gerente/Agente: apenas chats dos seus departamentos
    """
    message = 'Você não tem permissão para acessar este chat.'

    def has_permission(self, request, view):
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Todos os roles podem acessar chat (mas filtrado por departamento)
        return user.is_admin or user.is_gerente or user.is_agente

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Admin tem acesso total
        if user.is_admin:
            return True
        
        # Extrair department do chat/mensagem
        department = None
        if hasattr(obj, 'department'):
            department = obj.department
        elif hasattr(obj, 'chat') and hasattr(obj.chat, 'department'):
            department = obj.chat.department
        
        # Verifica se user pertence ao departamento
        if department:
            return user.departments.filter(id=department.id).exists()
        
        # Se não tem departamento definido, apenas admin pode acessar
        return False


class CanAccessAgenda(permissions.BasePermission):
    """
    Verifica se o usuário pode acessar agenda/tarefas.
    
    Regras:
    1. Se o usuário tem acesso ao chat (admin, gerente ou agente) → tem acesso à agenda
    2. OU se o tenant tem o produto workflow ativo → tem acesso à agenda
    
    Isso permite que usuários com acesso ao chat também tenham acesso à agenda,
    mesmo que o tenant não tenha o produto workflow explicitamente habilitado.
    """
    message = 'Você não tem permissão para acessar a agenda.'

    def has_permission(self, request, view):
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Verificar se o usuário tem acesso ao chat
        can_access_chat = user.is_admin or user.is_gerente or user.is_agente
        if can_access_chat:
            return True
        
        # Se não tem acesso ao chat, verificar se o tenant tem produto workflow
        if hasattr(user, 'tenant') and user.tenant:
            return user.tenant.can_access_product('workflow')
        
        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Admin tem acesso total
        if user.is_admin:
            return True
        
        # Verificar se o usuário tem acesso ao chat
        can_access_chat = user.is_admin or user.is_gerente or user.is_agente
        if can_access_chat:
            # Se tem acesso ao chat, verificar se pode acessar o departamento da tarefa
            department = getattr(obj, 'department', None)
            if department:
                return user.departments.filter(id=department.id).exists()
            # Se não tem departamento, apenas admin pode acessar
            return False
        
        # Se não tem acesso ao chat, verificar se o tenant tem produto workflow
        if hasattr(user, 'tenant') and user.tenant:
            if user.tenant.can_access_product('workflow'):
                # Com workflow, verificar departamento também
                department = getattr(obj, 'department', None)
                if department:
                    return user.departments.filter(id=department.id).exists()
                return True
        
        return False
