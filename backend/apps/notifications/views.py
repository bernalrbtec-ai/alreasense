import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.db import models

logger = logging.getLogger(__name__)

from .models import (
    NotificationTemplate, WhatsAppInstance, WhatsAppTemplate, NotificationLog, SMTPConfig,
    WhatsAppConnectionLog, UserNotificationPreferences, DepartmentNotificationPreferences
)
from .serializers import (
    NotificationTemplateSerializer,
    WhatsAppInstanceSerializer,
    WhatsAppTemplateSerializer,
    NotificationLogSerializer,
    SendNotificationSerializer,
    SMTPConfigSerializer,
    TestSMTPSerializer,
    WhatsAppConnectionLogSerializer,
    UserNotificationPreferencesSerializer,
    DepartmentNotificationPreferencesSerializer
)
from .permissions import CanManageDepartmentNotifications
from apps.billing.decorators import require_product

User = get_user_model()


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for NotificationTemplate."""
    
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Superadmin can see all templates
        if user.is_superuser or user.is_staff:
            return NotificationTemplate.objects.select_related('tenant', 'created_by').all()
        
        # Regular users see only their tenant templates and global templates
        return NotificationTemplate.objects.filter(
            models.Q(tenant=user.tenant) | models.Q(is_global=True)
        ).select_related('tenant', 'created_by')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test a template with sample context."""
        template = self.get_object()
        context = request.data.get('context', {})
        
        try:
            rendered = template.render(context)
            return Response({
                'success': True,
                'rendered': rendered
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get available template categories."""
        categories = [
            {'value': choice[0], 'label': choice[1]}
            for choice in NotificationTemplate.CATEGORY_CHOICES
        ]
        return Response(categories)


class WhatsAppInstanceViewSet(viewsets.ModelViewSet):
    """ViewSet for WhatsAppInstance (COM CACHE)."""
    
    serializer_class = WhatsAppInstanceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination
    
    def get_queryset(self):
        from apps.common.cache_manager import CacheManager
        import logging
        
        logger = logging.getLogger(__name__)
        user = self.request.user
        
        # REGRA: Cada cliente vê APENAS seus dados
        # Superadmin NÃO vê dados individuais de clientes
        if not user.tenant:
            # Superadmin sem tenant = sem acesso a dados de clientes
            logger.warning(f"⚠️ [INSTANCES] Usuário {user.email} sem tenant, retornando queryset vazio")
            return WhatsAppInstance.objects.none()
        
        # ✅ MELHORIA: Verificar se é uma requisição GET após POST/PATCH/DELETE
        # Se sim, sempre buscar do banco para garantir dados atualizados
        force_refresh = self.request.GET.get('_refresh', 'false').lower() == 'true'
        
        # Cache key por tenant
        cache_key = CacheManager.make_key(
            CacheManager.PREFIX_INSTANCE,
            'tenant',
            tenant_id=user.tenant.id
        )
        
        def fetch_instance_ids():
            """Função para buscar IDs de instâncias do banco"""
            queryset = WhatsAppInstance.objects.filter(tenant=user.tenant).select_related('tenant', 'created_by')
            ids = list(queryset.values_list('id', flat=True))
            logger.info(f"📋 [INSTANCES] Buscadas {len(ids)} instâncias do banco para tenant {user.tenant.id}")
            return ids
        
        # ✅ MELHORIA: Se forçar refresh ou cache não existir, buscar do banco diretamente
        if force_refresh:
            logger.info(f"🔄 [INSTANCES] Refresh forçado, buscando diretamente do banco")
            # Invalidar cache antes de buscar
            try:
                CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_INSTANCE}:*")
            except Exception as e:
                logger.error(f"❌ [INSTANCES] Erro ao invalidar cache: {e}")
            
            # Buscar diretamente do banco
            queryset = WhatsAppInstance.objects.filter(tenant=user.tenant).select_related('tenant', 'created_by')
        else:
            # ✅ OTIMIZAÇÃO: Cachear IDs (TTL de 1 minuto - dados mudam muito frequentemente)
            instance_ids = CacheManager.get_or_set(
                cache_key,
                fetch_instance_ids,
                ttl=CacheManager.TTL_MINUTE * 1  # Reduzido de 2 para 1 minuto
            )
            
            # ✅ CORREÇÃO: Se cache retornou vazio ou None, buscar diretamente do banco
            if not instance_ids or len(instance_ids) == 0:
                logger.warning(f"⚠️ [INSTANCES] Cache retornou vazio para tenant {user.tenant.id}, buscando diretamente do banco")
                # Invalidar cache corrompido
                try:
                    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_INSTANCE}:*")
                except Exception as e:
                    logger.error(f"❌ [INSTANCES] Erro ao invalidar cache: {e}")
                
                # Buscar diretamente do banco (bypass do cache)
                queryset = WhatsAppInstance.objects.filter(tenant=user.tenant).select_related('tenant', 'created_by')
            else:
                # ✅ MELHORIA: Verificar se há novos registros no banco
                db_count = WhatsAppInstance.objects.filter(tenant=user.tenant).count()
                
                # Se o número no banco é maior que no cache, buscar do banco
                if db_count > len(instance_ids):
                    logger.warning(f"⚠️ [INSTANCES] Banco tem {db_count} instâncias mas cache tem {len(instance_ids)}, buscando do banco")
                    try:
                        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_INSTANCE}:*")
                    except Exception as e:
                        logger.error(f"❌ [INSTANCES] Erro ao invalidar cache: {e}")
                    
                    queryset = WhatsAppInstance.objects.filter(tenant=user.tenant).select_related('tenant', 'created_by')
                else:
                    # ✅ OTIMIZAÇÃO: Reconstruir queryset com select_related
                    queryset = WhatsAppInstance.objects.filter(
                        id__in=instance_ids,
                        tenant=user.tenant
                    ).select_related('tenant', 'created_by')
        
        count = queryset.count()
        logger.info(f"✅ [INSTANCES] Retornando {count} instâncias para usuário {user.email}")
        return queryset
    
    def perform_create(self, serializer):
        """Ao criar, verificar limites, logar e invalidar cache."""
        from apps.common.cache_manager import CacheManager
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Verificar limite de instâncias antes de criar
        tenant = self.request.tenant
        if tenant:
            can_create, message = tenant.can_create_instance()
            if not can_create:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'error': message})
        
        # Criar a instância
        instance = serializer.save(created_by=self.request.user)
        logger.info(f"✅ [INSTANCES] Instância criada: {instance.friendly_name} (ID: {instance.id})")
        
        # Log da criação
        from .models import WhatsAppConnectionLog
        WhatsAppConnectionLog.objects.create(
            instance=instance,
            action='created',
            details='Instância WhatsApp criada',
            user=self.request.user
        )
        
        # ✅ INVALIDAR CACHE: Limpar cache de instâncias do tenant de forma mais agressiva
        try:
            CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_INSTANCE}:*")
            logger.info(f"🔄 [INSTANCES] Cache invalidado após criar instância {instance.friendly_name}")
        except Exception as e:
            logger.error(f"❌ [INSTANCES] Erro ao invalidar cache: {e}")
        
        return instance
    
    def perform_update(self, serializer):
        """Ao atualizar, invalidar cache."""
        from apps.common.cache_manager import CacheManager
        
        serializer.save()
        
        # ✅ INVALIDAR CACHE: Limpar cache de instâncias do tenant
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_INSTANCE}:*")
    
    def perform_destroy(self, instance):
        """Ao deletar, invalidar cache."""
        from apps.common.cache_manager import CacheManager
        
        instance.delete()
        
        # ✅ INVALIDAR CACHE: Limpar cache de instâncias do tenant
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_INSTANCE}:*")
    
    def perform_destroy(self, instance):
        """
        Override destroy to also delete from Evolution API.
        Padrão whatsapp-orchestrator: deletar da Evolution API antes de deletar do banco.
        """
        import requests
        from apps.connections.models import EvolutionConnection
        
        # Buscar servidor Evolution global
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        
        if evolution_server and evolution_server.base_url and evolution_server.api_key:
            try:
                # Deletar instância da Evolution API usando API MASTER
                api_url = evolution_server.base_url
                api_master = evolution_server.api_key
                
                print(f"🗑️  Deletando instância {instance.instance_name} da Evolution API...")
                
                delete_response = requests.delete(
                    f"{api_url}/instance/delete/{instance.instance_name}",
                    headers={'apikey': api_master},
                    timeout=10
                )
                
                if delete_response.status_code in [200, 204]:
                    print(f"✅ Instância deletada da Evolution API")
                    
                    # Log da deleção
                    WhatsAppConnectionLog.objects.create(
                        instance=instance,
                        action='deleted',
                        details='Instância deletada da Evolution API e do sistema',
                        user=self.request.user
                    )
                else:
                    print(f"⚠️  Erro ao deletar da Evolution API (Status {delete_response.status_code}): {delete_response.text[:200]}")
                    # Continuar mesmo se falhar na Evolution API
                    
            except Exception as e:
                print(f"⚠️  Exceção ao deletar da Evolution API: {str(e)}")
                # Continuar mesmo se falhar
        
        # Deletar do banco de dados
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def check_status(self, request, pk=None):
        """Check instance status."""
        instance = self.get_object()
        
        try:
            success = instance.check_connection_status()
            serializer = self.get_serializer(instance)
            
            return Response({
                'success': success,
                'instance': serializer.data,
                'connection_state': instance.connection_state,
                'phone_number': instance.phone_number,
                'status': instance.status
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'success': False,
                'error': f'Erro ao verificar status: {str(e)}',
                'details': instance.last_error
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def update_webhook(self, request, pk=None):
        """Update webhook configuration for this instance."""
        instance = self.get_object()
        
        try:
            success = instance.update_webhook_config()
            
            if success:
                return Response({
                    'success': True,
                    'message': 'Webhook atualizado com sucesso! Events e Base64 ativados.',
                })
            else:
                return Response({
                    'success': False,
                    'message': instance.last_error or 'Erro ao atualizar webhook',
                    'error': instance.last_error,
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Erro ao atualizar webhook: {str(e)}',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set this instance as default for the tenant."""
        instance = self.get_object()
        
        # Remove default from other instances of same tenant
        WhatsAppInstance.objects.filter(
            tenant=instance.tenant,
            is_default=True
        ).update(is_default=False)
        
        instance.is_default = True
        instance.save()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_test(self, request, pk=None):
        """Send a test message via provider (Evolution or Meta)."""
        instance = self.get_object()
        phone = request.data.get('phone')
        message = request.data.get('message', 'Teste de notificação do Alrea Sense')
        integration_type = getattr(instance, 'integration_type', None) or 'evolution'
        logger.info(
            "send_test: instance_id=%s integration_type=%s phone=%s",
            str(instance.id),
            integration_type,
            (phone or '')[:4] + '***' if phone and len(phone) > 4 else (phone or ''),
        )
        if not phone:
            return Response({'success': False, 'error': 'Número de telefone obrigatório'}, status=status.HTTP_400_BAD_REQUEST)
        from apps.notifications.whatsapp_providers import get_sender
        sender = get_sender(instance)
        if not sender:
            logger.warning(
                "send_test: provider não disponível instance_id=%s integration_type=%s (verifique Meta: phone_number_id e access_token)",
                str(instance.id),
                integration_type,
            )
            return Response({
                'success': False,
                'error': 'Provider não disponível para esta instância (verifique Phone Number ID e Access Token para Meta)'
            }, status=status.HTTP_400_BAD_REQUEST)
        try:
            logger.info("send_test: enviando via provider instance_id=%s", str(instance.id))
            # Meta: fora da janela 24h só aceita template; usar hello_world para teste (igual ao curl que funciona)
            if integration_type == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD and hasattr(sender, 'send_template'):
                ok, data = sender.send_template(phone.strip(), 'hello_world', 'en_US', [])
            else:
                ok, data = sender.send_text(phone.strip(), message)
            if ok:
                logger.info("send_test: mensagem enviada com sucesso instance_id=%s", str(instance.id))
                return Response({'success': True, 'message': 'Mensagem de teste enviada com sucesso', 'data': data})
            err = data.get('error', str(data))[:500]
            logger.warning("send_test: falha no envio instance_id=%s error=%s", str(instance.id), err)
            return Response({
                'success': False,
                'error': err
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("send_test: exceção instance_id=%s: %s", str(instance.id), e)
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def validate_meta(self, request, pk=None):
        """Valida Phone Number ID e Access Token da instância Meta (chamada à Graph API)."""
        instance = self.get_object()
        if getattr(instance, 'integration_type', None) != WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
            return Response({
                'success': False,
                'error': 'Esta instância não é do tipo API oficial Meta'
            }, status=status.HTTP_400_BAD_REQUEST)
        phone_number_id = (instance.phone_number_id or '').strip()
        access_token = (instance.access_token or '').strip()
        if not phone_number_id or not access_token:
            return Response({
                'success': False,
                'error': 'Phone Number ID e Access Token são obrigatórios'
            }, status=status.HTTP_400_BAD_REQUEST)
        import requests
        url = f"https://graph.facebook.com/v21.0/{phone_number_id}"
        try:
            r = requests.get(url, headers={'Authorization': f'Bearer {access_token}'}, timeout=10)
            data = r.json() if r.text else {}
            if r.status_code == 200:
                return Response({
                    'success': True,
                    'message': 'Token e Phone Number ID válidos',
                    'data': data
                })
            err = data.get('error', {})
            msg = err.get('message', r.text or 'Erro desconhecido')
            return Response({
                'success': False,
                'error': msg,
                'code': err.get('code')
            }, status=status.HTTP_400_BAD_REQUEST)
        except requests.RequestException as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
    
    @action(detail=True, methods=['post'])
    def generate_qr(self, request, pk=None):
        """Generate QR code for connection (Evolution only; Meta no-op)."""
        instance = self.get_object()
        if getattr(instance, 'integration_type', None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
            return Response({
                'success': False,
                'error': 'Instância API oficial Meta não usa QR Code. Use o botão Validar para testar token.'
            }, status=status.HTTP_400_BAD_REQUEST)
        try:
            qr_code = instance.generate_qr_code()
            if qr_code:
                return Response({
                    'success': True,
                    'qr_code': qr_code,
                    'expires_at': instance.qr_code_expires_at,
                    'message': 'QR code gerado com sucesso'
                })
            else:
                # Mostrar o erro detalhado que está no last_error da instância
                error_message = instance.last_error or 'Falha ao gerar QR code'
                return Response({
                    'success': False,
                    'error': error_message
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def disconnect(self, request, pk=None):
        """Disconnect the instance."""
        instance = self.get_object()
        
        try:
            success = instance.disconnect(user=request.user)
            
            if success:
                return Response({
                    'success': True,
                    'message': 'Instância desconectada com sucesso'
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Falha ao desconectar instância'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get connection logs for this instance."""
        instance = self.get_object()
        logs = instance.connection_logs.all()[:50]  # Last 50 logs
        
        serializer = WhatsAppConnectionLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def check_status(self, request, pk=None):
        """Check connection status and update phone number if connected."""
        instance = self.get_object()
        
        try:
            success = instance.check_connection_status()
            
            if success:
                serializer = self.get_serializer(instance)
                return Response({
                    'success': True,
                    'message': 'Status verificado com sucesso',
                    'instance': serializer.data
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Falha ao verificar status da conexão'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class WhatsAppTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for WhatsAppTemplate (templates Meta para janela 24h)."""
    serializer_class = WhatsAppTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.tenant:
            return WhatsAppTemplate.objects.none()
        qs = WhatsAppTemplate.objects.filter(tenant=user.tenant).select_related('tenant', 'wa_instance')
        wa_instance_id = self.request.query_params.get('wa_instance')
        if wa_instance_id:
            qs = qs.filter(models.Q(wa_instance_id=wa_instance_id) | models.Q(wa_instance__isnull=True))
        return qs.order_by('name')


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for NotificationLog (read-only)."""
    
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Superadmin can see all logs
        if user.is_superuser or user.is_staff:
            return NotificationLog.objects.select_related(
                'tenant',
                'template',
                'whatsapp_instance',
                'recipient'
            ).all()
        
        # Regular users see only their tenant logs
        return NotificationLog.objects.filter(
            tenant=user.tenant
        ).select_related(
            'tenant',
            'template',
            'whatsapp_instance',
            'recipient'
        )
    
    @action(detail=False, methods=['post'])
    def send(self, request):
        """Send a notification."""
        serializer = SendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        template_id = serializer.validated_data['template_id']
        recipient_id = serializer.validated_data['recipient_id']
        context = serializer.validated_data.get('context', {})
        scheduled_at = serializer.validated_data.get('scheduled_at')
        
        try:
            template = NotificationTemplate.objects.get(id=template_id)
            recipient = User.objects.get(id=recipient_id)
            
            # Import task to avoid circular dependency
            # from .tasks import send_notification_task  # Removido - Celery deletado
            
            # Queue notification task
            # task = send_notification_task.apply_async(
            #     args=[str(template.id), recipient.id, context],
            #     eta=scheduled_at
            # )
            # TODO: Implementar com RabbitMQ
            
            return Response({
                'success': True,
                'message': 'Notificação agendada para envio',
                'task_id': 'rabbitmq_implementation_pending'
            })
        
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get notification statistics."""
        user = request.user
        
        queryset = self.get_queryset()
        
        total = queryset.count()
        sent = queryset.filter(status='sent').count()
        failed = queryset.filter(status='failed').count()
        pending = queryset.filter(status='pending').count()
        
        by_type = {}
        for type_choice in NotificationLog.TYPE_CHOICES:
            type_code = type_choice[0]
            by_type[type_code] = queryset.filter(type=type_code).count()
        
        return Response({
            'total': total,
            'sent': sent,
            'failed': failed,
            'pending': pending,
            'by_type': by_type
        })


class SMTPConfigViewSet(viewsets.ModelViewSet):
    """ViewSet for SMTP Configuration."""
    
    serializer_class = SMTPConfigSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # REGRA: Cada cliente vê APENAS seus dados
        if not user.tenant:
            return SMTPConfig.objects.none()
        
        return SMTPConfig.objects.filter(tenant=user.tenant).select_related('tenant', 'created_by')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test SMTP configuration by sending a test email."""
        smtp_config = self.get_object()
        serializer = TestSMTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        test_email = serializer.validated_data['test_email']
        
        try:
            success, message = smtp_config.test_connection(test_email)
            
            # Refresh the object to get updated test status
            smtp_config.refresh_from_db()
            
            response_serializer = self.get_serializer(smtp_config)
            
            return Response({
                'success': success,
                'message': message,
                'smtp_config': response_serializer.data
            }, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set this SMTP config as default for the tenant."""
        smtp_config = self.get_object()
        
        # Remove default from other configs of same tenant
        SMTPConfig.objects.filter(
            tenant=smtp_config.tenant,
            is_default=True
        ).update(is_default=False)
        
        smtp_config.is_default = True
        smtp_config.save()
        
        serializer = self.get_serializer(smtp_config)
        return Response(serializer.data)


# ========== SISTEMA DE NOTIFICAÇÕES PERSONALIZADAS ==========

class UserNotificationPreferencesViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar preferências de notificação do usuário.
    """
    serializer_class = UserNotificationPreferencesSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserNotificationPreferences.objects.filter(
            user=self.request.user,
            tenant=self.request.user.tenant
        )
    
    def get_object(self):
        # Sempre retorna ou cria as preferências do usuário atual
        obj, created = UserNotificationPreferences.objects.get_or_create(
            user=self.request.user,
            tenant=self.request.user.tenant,
            defaults={
                'daily_summary_enabled': False,
                'agenda_reminder_enabled': False,
            }
        )
        return obj
    
    @action(detail=False, methods=['get', 'patch', 'put'])
    def mine(self, request):
        """Retorna ou atualiza as preferências do usuário atual."""
        import logging
        logger = logging.getLogger(__name__)
        
        obj, created = UserNotificationPreferences.objects.get_or_create(
            user=request.user,
            tenant=request.user.tenant,
            defaults={
                'daily_summary_enabled': False,
                'agenda_reminder_enabled': False,
            }
        )
        
        if request.method in ['PATCH', 'PUT']:
            logger.info(f'🔄 [NOTIFICATION PREFERENCES] Atualizando preferências para {request.user.email}')
            logger.info(f'   Dados recebidos: {request.data}')
            logger.info(f'   Estado atual: daily_summary_enabled={obj.daily_summary_enabled}, daily_summary_time={obj.daily_summary_time}, agenda_reminder_enabled={obj.agenda_reminder_enabled}, agenda_reminder_time={obj.agenda_reminder_time}')
            
            serializer = self.get_serializer(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            
            # Recarregar do banco para confirmar salvamento
            obj.refresh_from_db()
            logger.info(f'   ✅ Após salvar: daily_summary_enabled={obj.daily_summary_enabled}, daily_summary_time={obj.daily_summary_time}, agenda_reminder_enabled={obj.agenda_reminder_enabled}, agenda_reminder_time={obj.agenda_reminder_time}')
            
            return Response(serializer.data)
        
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def send_daily_summary_now(self, request):
        """
        Força o envio manual do resumo diário para o usuário atual.
        Útil para testes e disparos manuais.
        """
        import logging
        from django.utils import timezone
        from apps.campaigns.apps import CampaignsConfig
        
        logger = logging.getLogger(__name__)
        
        try:
            # Buscar preferências do usuário
            obj, created = UserNotificationPreferences.objects.get_or_create(
                user=request.user,
                tenant=request.user.tenant,
                defaults={
                    'daily_summary_enabled': False,
                    'agenda_reminder_enabled': False,
                }
            )
            
            # Verificar se resumo diário está habilitado
            if not obj.daily_summary_enabled:
                return Response({
                    'success': False,
                    'message': 'Resumo diário não está habilitado. Ative nas configurações primeiro.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verificar se há canais habilitados
            from apps.notifications.services import check_channels_enabled
            _, _, _, has_any = check_channels_enabled(obj, request.user)
            
            if not has_any:
                return Response({
                    'success': False,
                    'message': 'Nenhum canal de notificação está habilitado. Configure pelo menos um canal nas preferências.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Obter data atual no timezone local
            local_now = timezone.localtime(timezone.now())
            current_date = local_now.date()
            
            # Criar instância temporária do CampaignsConfig para acessar métodos
            config = CampaignsConfig('campaigns', None)
            
            # Chamar função de envio diretamente
            logger.info(f'📤 [MANUAL SEND] Enviando resumo diário manual para {request.user.email}')
            config.send_user_daily_summary(request.user, obj, current_date)
            
            return Response({
                'success': True,
                'message': 'Resumo diário enviado com sucesso! Verifique seu WhatsApp.'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'❌ [MANUAL SEND] Erro ao enviar resumo diário manual: {e}', exc_info=True)
            return Response({
                'success': False,
                'message': f'Erro ao enviar resumo diário: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DepartmentNotificationPreferencesViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar preferências de notificação do departamento.
    Apenas gestores podem configurar.
    """
    serializer_class = DepartmentNotificationPreferencesSerializer
    permission_classes = [IsAuthenticated, CanManageDepartmentNotifications]
    
    def get_queryset(self):
        from apps.authn.utils import get_user_managed_departments
        user = self.request.user
        
        managed_departments = get_user_managed_departments(user)
        
        return DepartmentNotificationPreferences.objects.filter(
            department__in=managed_departments,
            tenant=user.tenant
        ).select_related('department')
    
    @action(detail=False, methods=['get'])
    def my_departments(self, request):
        """Retorna preferências de todos os departamentos que o usuário gerencia."""
        from apps.authn.utils import get_user_managed_departments
        
        managed_departments = get_user_managed_departments(request.user)
        
        preferences = []
        for dept in managed_departments:
            pref, created = DepartmentNotificationPreferences.objects.get_or_create(
                department=dept,
                tenant=request.user.tenant,
                defaults={
                    'daily_summary_enabled': False,
                    'agenda_reminder_enabled': False,
                }
            )
            preferences.append(pref)
        
        serializer = self.get_serializer(preferences, many=True)
        return Response(serializer.data)

