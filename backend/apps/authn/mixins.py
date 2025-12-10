"""
Mixins para filtrar dados baseado em role e departamento.
"""
from django.db.models import Q


class DepartmentFilterMixin:
    """
    Mixin para filtrar querysets baseado nos departamentos do usuário.
    
    Admin: vê tudo do tenant
    Gerente/Agente: vê apenas dos seus departamentos
    """
    department_field = 'department'  # Campo que referencia o department no model
    
    def get_queryset(self):
        """Filtra queryset baseado no role e departamento do usuário."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Admin vê tudo do tenant
        if user.is_admin:
            return queryset
        
        # Pegar IDs dos departamentos do usuário
        department_ids = list(user.departments.values_list('id', flat=True))
        
        # Verificar se o modelo tem campo assigned_to
        has_assigned_to = hasattr(queryset.model, 'assigned_to')
        
        if department_ids:
            # ✅ Usuário tem departamentos: ver dados dos departamentos OU atribuídos diretamente a ele
            if has_assigned_to:
                # Incluir também itens atribuídos diretamente ao usuário
                return queryset.filter(
                    Q(**{f'{self.department_field}__in': department_ids}) |
                    Q(assigned_to=user)
                ).distinct()
            else:
                # Modelo não tem assigned_to, apenas filtrar por departamento
                filter_kwargs = {f'{self.department_field}__in': department_ids}
                return queryset.filter(**filter_kwargs)
        else:
            # ✅ Usuário SEM departamentos: ver apenas dados atribuídos diretamente a ele
            if has_assigned_to:
                return queryset.filter(assigned_to=user)
            else:
                # Se não tem departamentos e modelo não tem assigned_to, retornar vazio
                # (usuário não tem como ver nada)
                return queryset.none()


class MultiDepartmentFilterMixin:
    """
    Mixin para modelos que têm ManyToMany com departments.
    
    Exemplo: Contact pode estar em múltiplos departamentos
    """
    departments_field = 'departments'  # Campo ManyToMany
    
    def get_queryset(self):
        """Filtra queryset baseado nos departamentos do usuário."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Admin vê tudo do tenant
        if user.is_admin:
            return queryset
        
        # Gerente e Agente vêem apenas dos seus departamentos
        if user.is_gerente or user.is_agente:
            # Pegar IDs dos departamentos do usuário
            department_ids = user.departments.values_list('id', flat=True)
            
            # Filtrar por qualquer departamento em comum
            filter_kwargs = {f'{self.departments_field}__in': department_ids}
            return queryset.filter(**filter_kwargs).distinct()
        
        # Caso não tenha role definida, retorna vazio
        return queryset.none()


class TenantFilterMixin:
    """
    Mixin básico para filtrar apenas por tenant.
    Todos os usuários autenticados vêem dados do seu tenant.
    """
    
    def get_queryset(self):
        """Filtra queryset pelo tenant do usuário."""
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated and user.tenant:
            return queryset.filter(tenant=user.tenant)
        
        return queryset.none()


class MetricsPermissionMixin:
    """
    Mixin para views de métricas.
    Admin: todas as métricas do tenant
    Gerente: métricas filtradas por departamento
    Agente: sem acesso
    """
    
    def check_metrics_permission(self):
        """Verifica se o usuário pode visualizar métricas."""
        user = self.request.user
        
        if not user.is_authenticated:
            return False
        
        # Agente não pode ver métricas
        if user.is_agente:
            return False
        
        # Admin e Gerente podem
        return user.is_admin or user.is_gerente
    
    def filter_metrics_by_department(self, queryset):
        """
        Filtra métricas baseado no role.
        
        Args:
            queryset: QuerySet original
            
        Returns:
            QuerySet filtrado
        """
        user = self.request.user
        
        # Admin vê tudo
        if user.is_admin:
            return queryset
        
        # Gerente vê apenas dos seus departamentos
        if user.is_gerente:
            department_ids = user.departments.values_list('id', flat=True)
            return queryset.filter(
                Q(department__in=department_ids) |
                Q(departments__in=department_ids)
            ).distinct()
        
        # Outros roles não têm acesso
        return queryset.none()

