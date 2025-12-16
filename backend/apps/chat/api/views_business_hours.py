"""
Views para gerenciar horários de atendimento.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from apps.chat.models_business_hours import (
    BusinessHours,
    AfterHoursMessage,
    AfterHoursTaskConfig
)
from apps.chat.api.serializers_business_hours import (
    BusinessHoursSerializer,
    AfterHoursMessageSerializer,
    AfterHoursTaskConfigSerializer
)
from apps.chat.services.business_hours_service import BusinessHoursService
from apps.authn.permissions import CanAccessChat

logger = logging.getLogger(__name__)


class BusinessHoursViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar horários de atendimento.
    
    Permite configurar horários por tenant (geral) ou por departamento.
    """
    
    serializer_class = BusinessHoursSerializer
    permission_classes = [IsAuthenticated, CanAccessChat]
    
    def get_queryset(self):
        """Filtra por tenant do usuário."""
        user = self.request.user
        if not user.tenant:
            return BusinessHours.objects.none()
        
        queryset = BusinessHours.objects.filter(tenant=user.tenant).select_related(
            'tenant', 'department'
        )
        
        # Filtro opcional por departamento
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """
        ✅ CORREÇÃO: Faz upsert (update ou create) ao invés de sempre criar.
        Evita erro de constraint única quando já existe registro para o tenant/department.
        ✅ NOVO: Sincroniza is_active da mensagem automática após salvar BusinessHours.
        """
        tenant = self.request.user.tenant
        department = serializer.validated_data.get('department')
        
        # Buscar registro existente
        existing = BusinessHours.objects.filter(
            tenant=tenant,
            department=department
        ).first()
        
        if existing:
            # ✅ Atualizar registro existente (não atualizar tenant/department)
            logger.info(f"🔄 [BUSINESS HOURS] Atualizando registro existente (ID: {existing.id}) para tenant {tenant.name}, department: {department.name if department else 'Geral'}")
            serializer.instance = existing
            # Remover tenant e department do validated_data para não atualizar (já estão corretos)
            serializer.validated_data.pop('tenant', None)
            serializer.validated_data.pop('department', None)
            serializer.save()
            # ✅ CORREÇÃO CRÍTICA: Recarregar do banco para garantir dados atualizados
            serializer.instance.refresh_from_db()
            logger.info(f"✅ [BUSINESS HOURS] Registro atualizado e recarregado: ID={serializer.instance.id}")
        else:
            # ✅ Criar novo registro
            logger.info(f"➕ [BUSINESS HOURS] Criando novo registro para tenant {tenant.name}, department: {department.name if department else 'Geral'}")
            serializer.save(tenant=tenant)
            # ✅ CORREÇÃO CRÍTICA: Recarregar do banco para garantir dados atualizados
            serializer.instance.refresh_from_db()
            logger.info(f"✅ [BUSINESS HOURS] Registro criado e recarregado: ID={serializer.instance.id}")
        
        # ✅ NOVO: Sincronizar is_active da mensagem automática com BusinessHours
        self._sync_after_hours_message_status(tenant, department, serializer.instance.is_active)
    
    def perform_update(self, serializer):
        """
        ✅ CORREÇÃO: Garantir que objeto seja recarregado após atualização.
        ✅ NOVO: Sincroniza is_active da mensagem automática após atualizar BusinessHours.
        """
        logger.info(f"🔄 [BUSINESS HOURS] PATCH - Atualizando registro (ID: {serializer.instance.id})")
        old_is_active = serializer.instance.is_active
        serializer.save()
        # ✅ CORREÇÃO CRÍTICA: Recarregar do banco para garantir dados atualizados
        serializer.instance.refresh_from_db()
        logger.info(f"✅ [BUSINESS HOURS] Registro atualizado e recarregado: ID={serializer.instance.id}")
        
        # ✅ NOVO: Sincronizar is_active da mensagem automática se mudou
        if old_is_active != serializer.instance.is_active:
            self._sync_after_hours_message_status(
                serializer.instance.tenant,
                serializer.instance.department,
                serializer.instance.is_active
            )
    
    def _sync_after_hours_message_status(self, tenant, department, is_active):
        """
        Sincroniza o is_active da mensagem automática com o BusinessHours.
        
        ✅ MELHORIA: Sincroniza tanto mensagem específica do departamento quanto geral.
        Se department=None, sincroniza apenas a geral.
        Se department preenchido, sincroniza a específica E a geral (se existir).
        """
        try:
            # 1. Sincronizar mensagem específica do departamento (se department fornecido)
            if department:
                dept_message = AfterHoursMessage.objects.filter(
                    tenant=tenant,
                    department=department
                ).first()
                if dept_message and dept_message.is_active != is_active:
                    logger.info(
                        f"🔄 [BUSINESS HOURS] Sincronizando mensagem automática (departamento específico): "
                        f"is_active={dept_message.is_active} → {is_active} "
                        f"(tenant={tenant.name}, department={department.name})"
                    )
                    dept_message.is_active = is_active
                    dept_message.save(update_fields=['is_active'])
                    logger.info(f"✅ [BUSINESS HOURS] Mensagem automática (departamento específico) sincronizada")
            
            # 2. Sincronizar mensagem geral do tenant (sempre verificar)
            general_message = AfterHoursMessage.objects.filter(
                tenant=tenant,
                department__isnull=True
            ).first()
            if general_message:
                # Para mensagem geral, usar BusinessHours geral (não específico do departamento)
                general_bh = BusinessHoursService.get_business_hours(tenant, None)
                target_is_active = general_bh.is_active if general_bh else is_active
                
                if general_message.is_active != target_is_active:
                    logger.info(
                        f"🔄 [BUSINESS HOURS] Sincronizando mensagem automática (geral): "
                        f"is_active={general_message.is_active} → {target_is_active} "
                        f"(tenant={tenant.name})"
                    )
                    general_message.is_active = target_is_active
                    general_message.save(update_fields=['is_active'])
                    logger.info(f"✅ [BUSINESS HOURS] Mensagem automática (geral) sincronizada")
                else:
                    logger.debug(
                        f"ℹ️ [BUSINESS HOURS] Mensagem automática (geral) já está sincronizada "
                        f"(is_active={target_is_active})"
                    )
            
            if not department and not general_message:
                logger.debug(
                    f"ℹ️ [BUSINESS HOURS] Nenhuma mensagem automática encontrada para sincronizar "
                    f"(tenant={tenant.name}, department=Geral)"
                )
        except Exception as e:
            logger.error(
                f"❌ [BUSINESS HOURS] Erro ao sincronizar mensagem automática: {e}",
                exc_info=True
            )
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """
        Retorna horário atual (departamento específico ou geral do tenant).
        
        Query params:
        - department: ID do departamento (opcional)
        """
        user = request.user
        department_id = request.query_params.get('department')
        department = None
        
        if department_id:
            try:
                department = user.tenant.departments.get(id=department_id)
            except:
                pass
        
        business_hours = BusinessHoursService.get_business_hours(
            user.tenant,
            department
        )
        
        if not business_hours:
            return Response({
                'has_config': False,
                'message': 'Nenhum horário configurado'
            })
        
        serializer = BusinessHoursSerializer(business_hours)
        return Response({
            'has_config': True,
            'business_hours': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def check(self, request):
        """
        Verifica se está dentro do horário de atendimento.
        
        Query params:
        - department: ID do departamento (opcional)
        - datetime: Data/hora para verificar (opcional, formato ISO)
        """
        from django.utils.dateparse import parse_datetime
        
        user = request.user
        department_id = request.query_params.get('department')
        datetime_str = request.query_params.get('datetime')
        
        department = None
        if department_id:
            try:
                department = user.tenant.departments.get(id=department_id)
            except:
                pass
        
        check_datetime = None
        if datetime_str:
            check_datetime = parse_datetime(datetime_str)
        
        is_open, next_open_time = BusinessHoursService.is_business_hours(
            user.tenant,
            department,
            check_datetime
        )
        
        return Response({
            'is_open': is_open,
            'next_open_time': next_open_time
        })


class AfterHoursMessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar mensagens automáticas fora de horário.
    """
    
    serializer_class = AfterHoursMessageSerializer
    permission_classes = [IsAuthenticated, CanAccessChat]
    
    def get_queryset(self):
        """Filtra por tenant do usuário."""
        user = self.request.user
        if not user.tenant:
            return AfterHoursMessage.objects.none()
        
        queryset = AfterHoursMessage.objects.filter(tenant=user.tenant).select_related(
            'tenant', 'department'
        )
        
        # Filtro opcional por departamento
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """
        ✅ CORREÇÃO: Faz upsert (update ou create) ao invés de sempre criar.
        Evita erro de constraint única quando já existe registro para o tenant/department.
        ✅ NOVO: Sincroniza is_active com BusinessHours correspondente.
        """
        tenant = self.request.user.tenant
        department = serializer.validated_data.get('department')
        
        # ✅ NOVO: Buscar BusinessHours correspondente para sincronizar is_active
        # Remover is_active do validated_data se foi enviado (não deve ser editável)
        serializer.validated_data.pop('is_active', None)
        
        # Sincronizar is_active com BusinessHours correspondente
        business_hours = BusinessHoursService.get_business_hours(tenant, department)
        if business_hours:
            serializer.validated_data['is_active'] = business_hours.is_active
            logger.info(
                f"🔄 [AFTER HOURS MESSAGE] Sincronizando is_active com BusinessHours: "
                f"is_active={business_hours.is_active}"
            )
        else:
            # Se não há BusinessHours, usar True como padrão
            serializer.validated_data['is_active'] = True
            logger.warning(
                f"⚠️ [AFTER HOURS MESSAGE] BusinessHours não encontrado, usando is_active=True como padrão"
            )
        
        # Buscar registro existente
        existing = AfterHoursMessage.objects.filter(
            tenant=tenant,
            department=department
        ).first()
        
        if existing:
            # ✅ Atualizar registro existente (não atualizar tenant/department)
            logger.info(f"🔄 [AFTER HOURS MESSAGE] Atualizando registro existente (ID: {existing.id}) para tenant {tenant.name}, department: {department.name if department else 'Geral'}")
            logger.info(f"   📝 Dados recebidos: reply_to_groups={serializer.validated_data.get('reply_to_groups')}")
            serializer.instance = existing
            # Remover tenant e department do validated_data para não atualizar (já estão corretos)
            serializer.validated_data.pop('tenant', None)
            serializer.validated_data.pop('department', None)
            serializer.save()
            logger.info(f"   ✅ Após salvar: is_active={serializer.instance.is_active} (sincronizado), reply_to_groups={serializer.instance.reply_to_groups}")
        else:
            # ✅ Criar novo registro
            logger.info(f"➕ [AFTER HOURS MESSAGE] Criando novo registro para tenant {tenant.name}, department: {department.name if department else 'Geral'}")
            logger.info(f"   📝 Dados recebidos: reply_to_groups={serializer.validated_data.get('reply_to_groups')}")
            serializer.save(tenant=tenant)
            logger.info(f"   ✅ Após salvar: is_active={serializer.instance.is_active} (sincronizado), reply_to_groups={serializer.instance.reply_to_groups}")
    
    def perform_update(self, serializer):
        """
        ✅ CORREÇÃO: Garantir que is_active seja sincronizado com BusinessHours.
        ✅ NOVO: is_active não é mais editável - sempre sincroniza com BusinessHours.
        """
        logger.info(f"🔄 [AFTER HOURS MESSAGE] PATCH - Atualizando registro (ID: {serializer.instance.id})")
        logger.info(f"   📝 Dados recebidos: reply_to_groups={serializer.validated_data.get('reply_to_groups')}")
        
        # ✅ NOVO: Sincronizar is_active com BusinessHours (ignorar se foi enviado)
        business_hours = BusinessHoursService.get_business_hours(
            serializer.instance.tenant,
            serializer.instance.department
        )
        if business_hours:
            serializer.validated_data['is_active'] = business_hours.is_active
            logger.info(
                f"   🔄 Sincronizando is_active com BusinessHours: {business_hours.is_active}"
            )
        else:
            # Se não há BusinessHours, manter o valor atual ou usar True
            serializer.validated_data['is_active'] = serializer.instance.is_active if serializer.instance.is_active else True
            logger.warning(
                f"   ⚠️ BusinessHours não encontrado, mantendo is_active atual: {serializer.instance.is_active}"
            )
        
        # Remover is_active se foi enviado no request (não deve ser editável)
        if 'is_active' in serializer.validated_data:
            # Já foi definido acima com valor sincronizado
            pass
        
        logger.info(f"   📝 Estado atual no banco: is_active={serializer.instance.is_active}, reply_to_groups={getattr(serializer.instance, 'reply_to_groups', 'N/A')}")
        serializer.save()
        logger.info(f"   ✅ Após salvar: is_active={serializer.instance.is_active} (sincronizado), reply_to_groups={getattr(serializer.instance, 'reply_to_groups', 'N/A')}")
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """
        Retorna mensagem atual (departamento específico ou geral do tenant).
        
        ✅ MELHORIA: Sempre sincroniza is_active com BusinessHours antes de retornar.
        Retorna mensagem mesmo se inativa (para exibição no frontend).
        """
        user = request.user
        department_id = request.query_params.get('department')
        department = None
        
        if department_id:
            try:
                department = user.tenant.departments.get(id=department_id)
            except:
                pass
        
        # ✅ Buscar mensagem com sincronização automática
        message = BusinessHoursService.get_after_hours_message(
            user.tenant,
            department,
            sync_status=True  # Sincronizar is_active antes de retornar
        )
        
        if not message:
            return Response({
                'has_config': False,
                'message': 'Nenhuma mensagem configurada'
            })
        
        # ✅ Recarregar do banco para garantir dados atualizados após sincronização
        message.refresh_from_db()
        
        serializer = AfterHoursMessageSerializer(message)
        return Response({
            'has_config': True,
            'after_hours_message': serializer.data
        })


class AfterHoursTaskConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar configuração de tarefas automáticas fora de horário.
    """
    
    serializer_class = AfterHoursTaskConfigSerializer
    permission_classes = [IsAuthenticated, CanAccessChat]
    
    def get_queryset(self):
        """Filtra por tenant do usuário."""
        user = self.request.user
        if not user.tenant:
            return AfterHoursTaskConfig.objects.none()
        
        queryset = AfterHoursTaskConfig.objects.filter(tenant=user.tenant).select_related(
            'tenant', 'department', 'auto_assign_to_agent'
        )
        
        # Filtro opcional por departamento
        department_id = self.request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """
        ✅ CORREÇÃO: Faz upsert (update ou create) ao invés de sempre criar.
        Evita erro de constraint única quando já existe registro para o tenant/department.
        """
        tenant = self.request.user.tenant
        department = serializer.validated_data.get('department')
        
        # Buscar registro existente
        existing = AfterHoursTaskConfig.objects.filter(
            tenant=tenant,
            department=department
        ).first()
        
        if existing:
            # ✅ Atualizar registro existente (não atualizar tenant/department)
            logger.info(f"🔄 [AFTER HOURS TASK CONFIG] Atualizando registro existente (ID: {existing.id}) para tenant {tenant.name}, department: {department.name if department else 'Geral'}")
            serializer.instance = existing
            # Remover tenant e department do validated_data para não atualizar (já estão corretos)
            serializer.validated_data.pop('tenant', None)
            serializer.validated_data.pop('department', None)
            serializer.save()
        else:
            # ✅ Criar novo registro
            logger.info(f"➕ [AFTER HOURS TASK CONFIG] Criando novo registro para tenant {tenant.name}, department: {department.name if department else 'Geral'}")
            serializer.save(tenant=tenant)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """
        Retorna configuração atual (departamento específico ou geral do tenant).
        """
        user = request.user
        department_id = request.query_params.get('department')
        department = None
        
        if department_id:
            try:
                department = user.tenant.departments.get(id=department_id)
            except:
                pass
        
        config = BusinessHoursService.get_after_hours_task_config(
            user.tenant,
            department
        )
        
        if not config:
            return Response({
                'has_config': False,
                'message': 'Nenhuma configuração encontrada'
            })
        
        serializer = AfterHoursTaskConfigSerializer(config)
        return Response({
            'has_config': True,
            'task_config': serializer.data
        })

