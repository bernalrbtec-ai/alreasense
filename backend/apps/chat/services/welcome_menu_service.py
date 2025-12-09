"""
Serviço para gerenciar Menu de Boas-Vindas Automático
"""
import logging
from typing import Optional
from django.db import transaction
from apps.chat.models import Conversation, Message
from apps.chat.models_welcome_menu import WelcomeMenuConfig
from apps.authn.models import Department
from apps.notifications.models import WhatsAppInstance
from apps.chat.redis_queue import REDIS_QUEUE_SEND_MESSAGE

logger = logging.getLogger(__name__)


class WelcomeMenuService:
    """Serviço para gerenciar menu de boas-vindas automático"""
    
    @staticmethod
    def should_send_menu(conversation: Conversation) -> bool:
        """
        Verifica se deve enviar menu para uma conversa.
        
        Args:
            conversation: Conversa a verificar
        
        Returns:
            True se deve enviar menu, False caso contrário
        """
        try:
            config = WelcomeMenuConfig.objects.get(tenant=conversation.tenant)
        except WelcomeMenuConfig.DoesNotExist:
            return False
        
        if not config.enabled:
            return False
        
        # Verificar se já foi enviado menu recentemente (evitar spam)
        # Buscar última mensagem do sistema com menu
        last_menu_message = Message.objects.filter(
            conversation=conversation,
            is_internal=False,
            metadata__welcome_menu=True
        ).order_by('-created_at').first()
        
        if last_menu_message:
            # Se menu foi enviado há menos de 1 hora, não enviar novamente
            from django.utils import timezone
            from datetime import timedelta
            if timezone.now() - last_menu_message.created_at < timedelta(hours=1):
                logger.debug(f"⏭️ [WELCOME MENU] Menu já enviado recentemente para {conversation.id}")
                return False
        
        # Verificar condições
        if conversation.status == 'pending' and config.send_to_new_conversations:
            return True
        
        if conversation.status == 'closed' and config.send_to_closed_conversations:
            return True
        
        return False
    
    @staticmethod
    def send_welcome_menu(conversation: Conversation) -> Optional[Message]:
        """
        Envia menu de boas-vindas para uma conversa.
        
        Args:
            conversation: Conversa para enviar menu
        
        Returns:
            Message criada ou None se erro
        """
        try:
            config = WelcomeMenuConfig.objects.select_related('tenant').prefetch_related('departments').get(
                tenant=conversation.tenant
            )
        except WelcomeMenuConfig.DoesNotExist:
            logger.warning(f"⚠️ [WELCOME MENU] Config não encontrada para tenant {conversation.tenant.id}")
            return None
        
        if not config.enabled:
            logger.debug(f"⏭️ [WELCOME MENU] Menu desabilitado para tenant {conversation.tenant.id}")
            return None
        
        # Gerar texto do menu
        menu_text = config.get_menu_text()
        
        # Buscar instância WhatsApp ativa
        # ✅ CORREÇÃO: Não precisa de EvolutionConnection - usa configurações do .env
        try:
            wa_instance = WhatsAppInstance.objects.filter(
                tenant=conversation.tenant,
                is_active=True,
                status='active'
            ).first()
            
            if not wa_instance:
                logger.warning(f"⚠️ [WELCOME MENU] Instância WhatsApp não encontrada para tenant {conversation.tenant.id}")
                return None
            
            # ✅ CORREÇÃO: Verificar se configurações do .env estão disponíveis
            from django.conf import settings
            evolution_api_url = getattr(settings, 'EVOLUTION_API_URL', None)
            evolution_api_key = getattr(settings, 'EVOLUTION_API_KEY', None)
            
            if not evolution_api_url or not evolution_api_key:
                logger.warning(
                    f"⚠️ [WELCOME MENU] Configurações Evolution API não encontradas no .env "
                    f"(EVOLUTION_API_URL ou EVOLUTION_API_KEY) para tenant {conversation.tenant.id}"
                )
                return None
            
        except Exception as e:
            logger.error(f"❌ [WELCOME MENU] Erro ao buscar instância: {e}", exc_info=True)
            return None
        
        # Criar mensagem no banco
        try:
            with transaction.atomic():
                message = Message.objects.create(
                    conversation=conversation,
                    sender=None,  # Mensagem automática do sistema
                    content=menu_text,
                    direction='outgoing',
                    status='pending',
                    is_internal=False,
                    metadata={
                        'welcome_menu': True,
                        'welcome_menu_config_id': str(config.id),
                        'auto_sent': True
                    }
                )
                
                # Enfileirar envio via Redis
                from apps.chat.redis_queue import enqueue_message
                enqueue_message(REDIS_QUEUE_SEND_MESSAGE, {
                    'message_id': str(message.id),
                    'tenant_id': str(conversation.tenant.id)
                })
                
                logger.info(f"✅ [WELCOME MENU] Menu enfileirado para envio - conversa {conversation.id}, mensagem {message.id}")
                return message
                
        except Exception as e:
            logger.error(f"❌ [WELCOME MENU] Erro ao criar/enviar mensagem: {e}", exc_info=True)
            return None
    
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
        
        # Extrair número da resposta
        try:
            # Remover espaços e caracteres não numéricos, pegar primeiro número
            import re
            content = message.content or ''
            numbers = re.findall(r'\d+', content.strip())
            if not numbers:
                return False
            
            chosen_number = int(numbers[0])
        except (ValueError, IndexError):
            return False
        
        # Processar escolha
        if config.is_close_option(chosen_number):
            # Encerrar conversa
            return WelcomeMenuService._close_conversation(conversation)
        else:
            # Transferir para departamento
            department = config.get_department_by_number(chosen_number)
            if department:
                return WelcomeMenuService._transfer_to_department(conversation, department)
            else:
                logger.warning(f"⚠️ [WELCOME MENU] Número inválido escolhido: {chosen_number}")
                return False
    
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
        Fecha conversa.
        
        Args:
            conversation: Conversa a fechar
        
        Returns:
            True se fechou com sucesso
        """
        try:
            conversation.status = 'closed'
            conversation.save(update_fields=['status'])
            
            logger.info(f"✅ [WELCOME MENU] Conversa {conversation.id} fechada pelo cliente")
            return True
            
        except Exception as e:
            logger.error(f"❌ [WELCOME MENU] Erro ao fechar conversa: {e}", exc_info=True)
            return False

