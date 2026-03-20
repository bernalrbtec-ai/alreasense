"""
Serviço para gerenciar Menu de Boas-Vindas Automático - VERSÃO OTIMIZADA
"""
import logging
import re
from typing import Optional, Dict, Any
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from apps.chat.models import Conversation, Message
from apps.chat.models_welcome_menu import WelcomeMenuConfig, WelcomeMenuTimeout
from apps.authn.models import Department
from apps.notifications.models import WhatsAppInstance

logger = logging.getLogger(__name__)


class WelcomeMenuService:
    """Serviço otimizado para gerenciar menu de boas-vindas automático"""
    
    # Constantes
    CACHE_TIMEOUT_CONFIG = 300  # 5 minutos para cache da config
    MENU_SPAM_THRESHOLD = timedelta(hours=1)  # Intervalo mínimo entre menus
    MENU_RESPONSE_TIMEOUT = timedelta(hours=1)  # Tempo válido para resposta ao menu
    
    @staticmethod
    def should_send_menu(conversation: Conversation) -> bool:
        """
        Verifica se deve enviar menu (VERSÃO OTIMIZADA).
        
        ✅ MELHORIAS:
        - Verificações em ordem de custo (rápido → lento)
        - Cache da configuração
        - Métodos auxiliares para clareza
        - Horário de funcionamento respeitado
        
        Args:
            conversation: Conversa a verificar
        
        Returns:
            True se deve enviar menu, False caso contrário
        """
        logger.info(f"🔍 [WELCOME MENU] Verificando menu para conversa {conversation.id}")
        logger.debug(f"   Status: {conversation.status}, Dept: {conversation.department.name if conversation.department else 'None'}")
        
        # 1. Buscar config (com cache) - Rápido
        config = WelcomeMenuService._get_menu_config(conversation.tenant)
        if not config or not config.enabled:
            logger.debug("⏭️ Menu desabilitado ou config não encontrada")
            return False
        
        # 2. Verificar status (sem query) - Rápido
        if not WelcomeMenuService._should_send_for_status(conversation, config):
            return False
        
        # 3. Verificar spam (1 query) - Médio
        if WelcomeMenuService._was_menu_sent_recently(conversation):
            return False
        
        # 4. Verificar horário (múltiplas queries) - Lento
        if not WelcomeMenuService._is_within_business_hours(conversation):
            return False
        
        logger.info("✅ Todas as condições atendidas - enviará menu")
        return True
    
    @staticmethod
    def _get_menu_config(tenant) -> Optional[WelcomeMenuConfig]:
        """
        Busca config do menu com cache (NOVO).
        Cache de 5 minutos para reduzir queries.
        """
        cache_key = f"welcome_menu_config:{tenant.id}"
        config = cache.get(cache_key)
        
        if config is None:
            try:
                config = WelcomeMenuConfig.objects.get(tenant=tenant)
                cache.set(cache_key, config, WelcomeMenuService.CACHE_TIMEOUT_CONFIG)
                logger.debug(f"✅ Config carregada do DB e cacheada")
            except WelcomeMenuConfig.DoesNotExist:
                logger.warning(f"⚠️ Config não encontrada para tenant {tenant.id}")
                return None
        else:
            logger.debug("✅ Config carregada do cache")
        
        return config
    
    @staticmethod
    def _should_send_for_status(conversation: Conversation, config: WelcomeMenuConfig) -> bool:
        """
        Verifica se status da conversa permite envio (NOVO).
        Sem queries, apenas verificação de atributos.
        """
        if conversation.status == 'pending' and config.send_to_new_conversations:
            logger.info("✅ Status pending + send_to_new=True")
            return True
        
        if conversation.status == 'closed' and config.send_to_closed_conversations:
            logger.info("✅ Status closed + send_to_closed=True")
            return True
        
        logger.debug(f"⏭️ Status '{conversation.status}' não atende condições")
        return False
    
    @staticmethod
    def _was_menu_sent_recently(conversation: Conversation) -> bool:
        """
        Verifica se menu foi enviado recentemente - anti-spam (NOVO).
        1 query otimizada.
        """
        last_menu = Message.objects.filter(
            conversation=conversation,
            is_internal=False,
            metadata__welcome_menu=True
        ).order_by('-created_at').values('created_at').first()
        
        if not last_menu:
            return False
        
        time_since = timezone.now() - last_menu['created_at']
        if time_since < WelcomeMenuService.MENU_SPAM_THRESHOLD:
            logger.debug(f"⏭️ Menu enviado há {time_since.total_seconds() / 60:.1f}min (< 1h)")
            return True
        
        logger.debug(f"✅ Menu enviado há {time_since.total_seconds() / 3600:.1f}h (> 1h)")
        return False
    
    @staticmethod
    def _is_within_business_hours(conversation: Conversation) -> bool:
        """
        Verifica horário de funcionamento (NOVO).
        Múltiplas queries internas, por isso é feito por último.
        """
        try:
            from apps.chat.services.business_hours_service import BusinessHoursService
            
            is_open, next_open = BusinessHoursService.is_business_hours(
                tenant=conversation.tenant,
                department=conversation.department
            )
            
            if not is_open:
                logger.info(f"⏰ FORA do horário - próximo: {next_open}")
                logger.info("   Cliente receberá mensagem automática ao invés do menu")
                return False
            
            logger.info("✅ DENTRO do horário de atendimento")
            return True
            
        except Exception as e:
            # Fail-safe: se erro na verificação, permite enviar menu
            # Melhor enviar menu do que deixar cliente sem resposta
            logger.error(f"❌ Erro ao verificar horário: {e}", exc_info=True)
            logger.warning("⚠️ Fail-safe: permitindo envio do menu")
            return True
    
    @staticmethod
    def _create_and_send_message(
        conversation: Conversation,
        content: str,
        metadata: Dict[str, Any],
        log_prefix: str = "MESSAGE"
    ) -> Optional[Message]:
        """
        Método auxiliar DRY para criar e enfileirar mensagens (NOVO).
        Elimina duplicação de código entre os métodos de envio.
        
        Args:
            conversation: Conversa destino
            content: Conteúdo da mensagem
            metadata: Metadados da mensagem (será adicionado auto_sent=True)
            log_prefix: Prefixo para logs
        
        Returns:
            Message criada ou None se erro
        """
        try:
            with transaction.atomic():
                message = Message.objects.create(
                    conversation=conversation,
                    sender=None,  # Mensagem automática do sistema
                    content=content,
                    direction='outgoing',
                    status='pending',
                    is_internal=False,
                    metadata={**metadata, 'auto_sent': True}
                )
                
                logger.debug(f"✅ [{log_prefix}] Mensagem criada: {message.id}")
                
                # Enfileirar após commit (evita race condition)
                def enqueue_after_commit():
                    try:
                        from apps.chat.tasks import send_message_to_evolution
                        send_message_to_evolution.delay(str(message.id))
                        logger.info(f"✅ [{log_prefix}] Mensagem enfileirada: {message.id}")
                    except Exception as e:
                        logger.error(f"❌ [{log_prefix}] Erro ao enfileirar: {e}", exc_info=True)
                
                transaction.on_commit(enqueue_after_commit)
                return message
                
        except Exception as e:
            logger.error(f"❌ [{log_prefix}] Erro ao criar mensagem: {e}", exc_info=True)
            return None
    
    @staticmethod
    def send_welcome_menu(conversation: Conversation) -> Optional[Message]:
        """
        Envia menu de boas-vindas (VERSÃO OTIMIZADA).
        
        ✅ MELHORIAS:
        - Usa _create_and_send_message() (DRY)
        - Validações mais robustas
        """
        # Buscar config (com cache)
        config = WelcomeMenuService._get_menu_config(conversation.tenant)
        if not config or not config.enabled:
            logger.warning(f"⚠️ Menu desabilitado ou config não encontrada")
            return None
        
        # Validar instância WhatsApp
        wa_instance = WhatsAppInstance.objects.filter(
            tenant=conversation.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not wa_instance:
            logger.warning(f"⚠️ Instância WhatsApp não encontrada")
            return None
        
        # Validar configurações Evolution API
        evolution_api_url = getattr(settings, 'EVOLUTION_API_URL', None)
        evolution_api_key = getattr(settings, 'EVOLUTION_API_KEY', None)
        
        if not evolution_api_url or not evolution_api_key:
            logger.warning("⚠️ Configurações Evolution API não encontradas no .env")
            return None
        
        # Gerar texto do menu
        menu_text = config.get_menu_text()
        
        # Criar e enviar mensagem usando método auxiliar DRY
        message = WelcomeMenuService._create_and_send_message(
            conversation=conversation,
            content=menu_text,
            metadata={
                'welcome_menu': True,
                'welcome_menu_config_id': str(config.id)
            },
            log_prefix="WELCOME MENU"
        )
        
        if not message:
            return None
        
        # Criar timeout de inatividade (se habilitado)
        if config.inactivity_timeout_enabled:
            try:
                # Deletar timeout anterior se existir
                WelcomeMenuTimeout.objects.filter(
                    conversation=conversation,
                    is_active=True
                ).delete()
                
                # Criar novo timeout
                WelcomeMenuTimeout.objects.create(
                    conversation=conversation,
                    menu_sent_at=timezone.now(),
                    reminder_sent=False,
                    is_active=True
                )
                logger.debug("⏰ Timeout de inatividade criado")
            except Exception as e:
                logger.error(f"❌ Erro ao criar timeout: {e}", exc_info=True)
                # Não falhar o envio do menu por causa do timeout
        
        return message
    
    @staticmethod
    def process_menu_response(conversation: Conversation, message: Message) -> bool:
        """
        Processa resposta do cliente ao menu.
        
        Args:
            conversation: Conversa que recebeu a resposta
            message_content: Conteúdo da mensagem recebida
        
        Returns:
            True se processou com sucesso, False caso contrário
        """
        try:
            config = WelcomeMenuConfig.objects.select_related('tenant').prefetch_related('departments').get(
                tenant=conversation.tenant
            )
        except WelcomeMenuConfig.DoesNotExist:
            return False
        
        if not config.enabled:
            return False
        
        # Verificar se há menu pendente (enviado recentemente)
        last_menu_message = Message.objects.filter(
            conversation=conversation,
            is_internal=False,
            metadata__welcome_menu=True
        ).order_by('-created_at').first()
        
        if not last_menu_message:
            # Sem menu enviado, não processar
            return False
        
        # Verificar se resposta veio após o menu (dentro de 1 hora)
        from django.utils import timezone
        from datetime import timedelta
        if message.created_at - last_menu_message.created_at > timedelta(hours=1):
            # Resposta muito antiga, não processar
            return False
        
        # Validar e extrair número da resposta (VERSÃO SIMPLIFICADA)
        content = (message.content or '').strip()
        
        if not content:
            return False
        
        # Validação simples: deve ser apenas dígitos
        if not content.isdigit():
            logger.warning(f"⚠️ Resposta não numérica: '{content}'")
            return WelcomeMenuService._send_invalid_option_message(
                conversation, content, config
            )
        
        try:
            chosen_number = int(content)
        except ValueError:
            logger.warning(f"⚠️ Erro ao parsear número: '{content}'")
            return WelcomeMenuService._send_invalid_option_message(
                conversation, content, config
            )
        
        # ✅ NOVO: Cancelar timeout ativo (cliente respondeu)
        try:
            timeout = WelcomeMenuTimeout.objects.filter(
                conversation=conversation,
                is_active=True
            ).first()
            if timeout:
                timeout.is_active = False
                timeout.save(update_fields=['is_active', 'updated_at'])
                logger.info(f"✅ [WELCOME MENU] Timeout cancelado - cliente respondeu")
        except Exception as e:
            logger.error(f"❌ [WELCOME MENU] Erro ao cancelar timeout: {e}", exc_info=True)
        
        # Processar escolha
        if config.is_close_option(chosen_number):
            # ✅ CORREÇÃO: Encerrar conversa e retornar True
            logger.info(f"🔒 [WELCOME MENU] Cliente escolheu encerrar conversa {conversation.id}")
            success = WelcomeMenuService._close_conversation(conversation)
            if success:
                logger.info(f"✅ [WELCOME MENU] Conversa {conversation.id} encerrada com sucesso")
            else:
                logger.error(f"❌ [WELCOME MENU] Falha ao encerrar conversa {conversation.id}")
            return success
        else:
            # Transferir para departamento
            department = config.get_department_by_number(chosen_number)
            if department:
                logger.info(f"📋 [WELCOME MENU] Transferindo para departamento: {department.name}")
                return WelcomeMenuService._transfer_to_department(conversation, department)
            else:
                # ✅ Número inválido (fora do range de departamentos)
                logger.warning(f"⚠️ [WELCOME MENU] Número {chosen_number} inválido (fora do range)")
                return WelcomeMenuService._send_invalid_option_message(conversation, str(chosen_number), config)
    
    @staticmethod
    def _transfer_to_department(conversation: Conversation, department: Department) -> bool:
        """
        Transfere conversa para departamento.
        
        Args:
            conversation: Conversa a transferir
            department: Departamento destino
        
        Returns:
            True se transferiu com sucesso
        """
        try:
            from apps.chat.api.views import ConversationViewSet
            from apps.authn.models import User
            
            # Simular request para usar método transfer existente
            # Ou implementar transferência direta aqui
            conversation.department = department
            conversation.status = 'open'
            conversation.save(update_fields=['department', 'status'])
            
            logger.info(f"✅ [WELCOME MENU] Conversa {conversation.id} transferida para {department.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ [WELCOME MENU] Erro ao transferir conversa: {e}", exc_info=True)
            return False
    
    @staticmethod
    def _close_conversation(conversation: Conversation) -> bool:
        """
        Fecha conversa (VERSÃO OTIMIZADA).
        
        ✅ MELHORIAS:
        - Usa _create_and_send_message() (DRY)
        - Marca mensagens não lidas como lidas
        - Envia confirmação de encerramento
        """
        try:
            # Texto de confirmação
            confirmation_text = (
                "✅ Conversa encerrada.\n\n"
                "Obrigado pelo contato! Se precisar de algo, é só enviar uma nova mensagem."
            )
            
            # Enviar mensagem de confirmação usando método auxiliar
            message = WelcomeMenuService._create_and_send_message(
                conversation=conversation,
                content=confirmation_text,
                metadata={'welcome_menu_close_confirmation': True},
                log_prefix="CLOSE"
            )
            
            if not message:
                logger.error("❌ Falha ao criar mensagem de encerramento")
                return False
            
            # Marcar mensagens não lidas como lidas
            unread_count = Message.objects.filter(
                conversation=conversation,
                direction='incoming',
                status__in=['sent', 'delivered']
            ).update(status='seen')
            
            if unread_count > 0:
                logger.debug(f"✅ {unread_count} mensagens marcadas como lidas")
            
            # Fechar conversa e remover departamento/atendente (Inbox) para a Secretária poder responder quando reabrir
            from apps.chat.models_flow import ConversationFlowState
            from apps.chat.services.conversation_timeline import (
                merge_conversation_closed_on_instance,
                should_skip_timeline_for_conversation,
            )

            with transaction.atomic():
                locked = (
                    Conversation.objects.select_for_update()
                    .select_related("department", "assigned_to")
                    .get(pk=conversation.id)
                )
                if locked.status == "closed":
                    logger.info(f"✅ Conversa {conversation.id} já estava fechada")
                    return True
                if not should_skip_timeline_for_conversation(locked):
                    merge_conversation_closed_on_instance(
                        locked,
                        close_source="welcome_menu",
                        closed_by_user=None,
                    )
                locked.status = "closed"
                locked.department = None
                locked.assigned_to = None
                locked.save(
                    update_fields=[
                        "status",
                        "department",
                        "assigned_to",
                        "metadata",
                        "updated_at",
                    ]
                )
                ConversationFlowState.objects.filter(conversation_id=locked.id).delete()
            logger.info(f"✅ Conversa {conversation.id} fechada pelo cliente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao fechar conversa: {e}", exc_info=True)
            return False
    
    @staticmethod
    def _send_invalid_option_message(conversation: Conversation, invalid_input: str, config: WelcomeMenuConfig) -> bool:
        """
        Envia mensagem de opção inválida (VERSÃO OTIMIZADA).
        
        ✅ MELHORIAS:
        - Usa _create_and_send_message() (DRY)
        - Extração de opções melhorada
        """
        try:
            # Mensagem de erro
            error_text = (
                f"❌ Opção *\"{invalid_input}\"* inválida.\n\n"
                f"Por favor, escolha uma das opções abaixo digitando *apenas o número*:\n\n"
            )
            
            # Extrair apenas as opções do menu (sem boas-vindas)
            menu_text = config.get_menu_text()
            menu_lines = menu_text.split('\n')
            options_only = [
                line for line in menu_lines 
                if line.strip() and (line[0].isdigit() or line.startswith('Escolha'))
            ]
            
            full_message = error_text + '\n'.join(options_only)
            
            # Enviar mensagem usando método auxiliar
            message = WelcomeMenuService._create_and_send_message(
                conversation=conversation,
                content=full_message,
                metadata={
                    'welcome_menu_invalid_option': True,
                    'invalid_input': invalid_input
                },
                log_prefix="INVALID OPTION"
            )
            
            return message is not None
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem de opção inválida: {e}", exc_info=True)
            return False
    
    @staticmethod
    def _send_inactivity_reminder(conversation: Conversation, config: WelcomeMenuConfig) -> bool:
        """
        Envia lembrete de inatividade (VERSÃO OTIMIZADA).
        
        ✅ MELHORIAS:
        - Usa _create_and_send_message() (DRY)
        """
        try:
            remaining_minutes = config.auto_close_minutes - config.first_reminder_minutes
            
            reminder_text = (
                f"⏰ Você ainda está aí?\n\n"
                f"Digite *1* para continuar o atendimento ou aguarde que "
                f"encerraremos em *{remaining_minutes} minutos*."
            )
            
            # Enviar mensagem usando método auxiliar
            message = WelcomeMenuService._create_and_send_message(
                conversation=conversation,
                content=reminder_text,
                metadata={'welcome_menu_reminder': True},
                log_prefix="INACTIVITY REMINDER"
            )
            
            return message is not None
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar lembrete de inatividade: {e}", exc_info=True)
            return False

