"""
Views para Menu de Boas-Vindas
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.chat.models_welcome_menu import WelcomeMenuConfig
from apps.chat.api.serializers_welcome_menu import WelcomeMenuConfigSerializer
from apps.authn.models import Department

logger = logging.getLogger(__name__)


class WelcomeMenuConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar configuração do Menu de Boas-Vindas.
    
    Permite:
    - GET: Obter configuração atual do tenant
    - PUT/PATCH: Atualizar configuração
    - POST: Criar configuração (se não existir)
    """
    
    serializer_class = WelcomeMenuConfigSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Retorna apenas configuração do tenant do usuário"""
        return WelcomeMenuConfig.objects.filter(tenant=self.request.user.tenant)
    
    def get_object(self):
        """Retorna configuração do tenant ou cria uma nova"""
        try:
            return WelcomeMenuConfig.objects.get(tenant=self.request.user.tenant)
        except WelcomeMenuConfig.DoesNotExist:
            # Criar configuração padrão se não existir (desativada por padrão)
            return WelcomeMenuConfig.objects.create(
                tenant=self.request.user.tenant,
                enabled=False,  # ✅ Padrão: desativado
                welcome_message=f"Bem-vindo a {self.request.user.tenant.name}!",
                send_to_new_conversations=True,  # Se ativar, envia para novas
                send_to_closed_conversations=True  # Se ativar, envia para fechadas
            )
    
    def list(self, request):
        """Retorna configuração do tenant"""
        config = self.get_object()
        serializer = self.get_serializer(config)
        return Response(serializer.data)
    
    def create(self, request):
        """Criar ou atualizar configuração"""
        try:
            config = WelcomeMenuConfig.objects.get(tenant=request.user.tenant)
            # Se existe, atualizar
            serializer = self.get_serializer(config, data=request.data, partial=True)
        except WelcomeMenuConfig.DoesNotExist:
            # Se não existe, criar
            serializer = self.get_serializer(data=request.data)
        
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def preview(self, request):
        """
        Retorna preview do texto do menu baseado na configuração atual.
        
        Útil para visualizar como o menu ficará antes de habilitar.
        """
        config = self.get_object()
        menu_text = config.get_menu_text()
        
        return Response({
            'menu_text': menu_text,
            'departments_count': config.departments.count(),
            'has_close_option': config.show_close_option
        })
    
    @action(detail=False, methods=['get'])
    def available_departments(self, request):
        """
        Retorna lista de departamentos disponíveis do tenant.
        
        Útil para popular dropdown de seleção no frontend.
        """
        departments = Department.objects.filter(
            tenant=request.user.tenant
        ).order_by('name')
        
        serializer = WelcomeMenuConfigSerializer.DepartmentOptionSerializer(departments, many=True)
        return Response(serializer.data)

