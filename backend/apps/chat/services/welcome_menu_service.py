"""
Serviço para gerenciar Menu de Boas-Vindas Automático
"""
import logging
from typing import Optional
from django.db import transaction
from django.utils import timezone
from apps.chat.models import Conversation, Message
from apps.chat.models_welcome_menu import WelcomeMenuConfig, WelcomeMenuTimeout
from apps.authn.models import Department
from apps.notifications.models import WhatsAppInstance

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
        logger.info(f"🔍 [WELCOME MENU] Verificando se deve enviar menu para conversa {conversation.id}")
        logger.info(f"   📊 Status: {conversation.status}")
        logger.info(f"   📋 Departamento: {conversation.department.name if conversation.department else 'None'}")
        
        try:
            config = WelcomeMenuConfig.objects.get(tenant=conversation.tenant)
            logger.info(f"   ✅ Config encontrada: enabled={config.enabled}, send_to_new={config.send_to_new_conversations}, send_to_closed={config.send_to_closed_conversations}")
        except WelcomeMenuConfig.DoesNotExist:
            logger.warning(f"   ⚠️ [WELCOME MENU] Config não encontrada para tenant {conversation.tenant.id}")
            return False
        
        if not config.enabled:
            logger.debug(f"   ⏭️ [WELCOME MENU] Menu desabilitado na configuração")
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
            time_since_last = timezone.now() - last_menu_message.created_at
            if time_since_last < timedelta(hours=1):
                logger.debug(f"   ⏭️ [WELCOME MENU] Menu já enviado recentemente ({time_since_last.total_seconds() / 60:.1f} minutos atrás) para {conversation.id}")
                return False
            else:
                logger.info(f"   ✅ Menu anterior foi enviado há mais de 1 hora ({time_since_last.total_seconds() / 3600:.1f} horas atrás), pode enviar novamente")
        
        # Verificar condições
        if conversation.status == 'pending' and config.send_to_new_conversations:
            logger.info(f"   ✅ [WELCOME MENU] Condição atendida: status=pending e send_to_new_conversations=True")
            return True
        
        if conversation.status == 'closed' and config.send_to_closed_conversations:
            logger.info(f"   ✅ [WELCOME MENU] Condição atendida: status=closed e send_to_closed_conversations=True")
            return True
        
        logger.info(f"   ⏭️ [WELCOME MENU] Nenhuma condição atendida para enviar menu")
        logger.info(f"      Status: {conversation.status}")
        logger.info(f"      send_to_new_conversations: {config.send_to_new_conversations}")
        logger.info(f"      send_to_closed_conversations: {config.send_to_closed_conversations}")
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
                
                logger.info(f"✅ [WELCOME MENU] Mensagem criada: {message.id}")
                
                # ✅ CORREÇÃO CRÍTICA: Enfileira mensagem APENAS após commit da transação
                # Isso garante que a mensagem esteja no banco quando o worker tentar buscá-la
                # Evita race condition onde worker tenta buscar mensagem que ainda não foi commitada
                def enqueue_message_after_commit():
                    try:
                        from apps.chat.tasks import send_message_to_evolution
                        send_message_to_evolution.delay(str(message.id))
                        logger.info(f"✅ [WELCOME MENU] Menu enfileirado para envio - conversa {conversation.id}, mensagem {message.id}")
                    except Exception as e:
                        logger.error(f"❌ [WELCOME MENU] Erro ao enfileirar mensagem: {e}", exc_info=True)
                        # Não re-raise - mensagem já foi criada, pode ser enviada manualmente depois
                
                transaction.on_commit(enqueue_message_after_commit)
                
                # ✅ NOVO: Criar timeout de inatividade (se habilitado)
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
                        logger.info(f"⏰ [WELCOME MENU] Timeout criado para conversa {conversation.id}")
                    except Exception as e:
                        logger.error(f"❌ [WELCOME MENU] Erro ao criar timeout: {e}", exc_info=True)
                        # Não falhar o envio do menu por causa do timeout
                
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
            content_stripped = content.strip()
            
            # ✅ NOVO: Se não houver conteúdo, ignorar
            if not content_stripped:
                return False
            
            # Tentar extrair número
            numbers = re.findall(r'\d+', content_stripped)
            
            # ✅ NOVO: Se não encontrou número OU não é APENAS número, é inválido
            # Exemplo: "oi" → inválido, "ajuda" → inválido, "999" → válido se no menu
            is_pure_number = content_stripped.isdigit()
            
            if not numbers or not is_pure_number:
                # Não é um número válido, enviar mensagem de opção inválida
                logger.warning(f"⚠️ [WELCOME MENU] Resposta não numérica recebida: '{content_stripped}'")
                return WelcomeMenuService._send_invalid_option_message(
                    conversation, 
                    content_stripped,  # Passar o texto original
                    config
                )
            
            chosen_number = int(numbers[0])
        except (ValueError, IndexError):
            # Erro ao parsear, enviar mensagem de opção inválida
            logger.warning(f"⚠️ [WELCOME MENU] Erro ao parsear resposta: '{content}'")
            return WelcomeMenuService._send_invalid_option_message(
                conversation,
                content.strip() if content else "resposta vazia",
                config
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
        Fecha conversa.
        
        ✅ NOVO: Marca todas as mensagens não lidas como lidas ao fechar conversa.
        Isso evita que conversas fechadas apareçam no contador de "conversas novas".
        
        ✅ CORREÇÃO: Envia mensagem de confirmação antes de fechar.
        
        Args:
            conversation: Conversa a fechar
        
        Returns:
            True se fechou com sucesso
        """
        from django.db import transaction
        from apps.chat.models import Message
        
        try:
            # ✅ NOVO: Enviar mensagem de confirmação de encerramento
            confirmation_text = (
                "✅ Conversa encerrada.\n\n"
                "Obrigado pelo contato! Se precisar de algo, é só enviar uma nova mensagem."
            )
            
            with transaction.atomic():
                # Criar mensagem de confirmação
                confirmation_message = Message.objects.create(
                    conversation=conversation,
                    sender=None,
                    content=confirmation_text,
                    direction='outgoing',
                    status='pending',
                    is_internal=False,
                    metadata={
                        'welcome_menu_close_confirmation': True,
                        'auto_sent': True
                    }
                )
                
                # Enfileirar para envio
                def enqueue_confirmation():
                    try:
                        from apps.chat.tasks import send_message_to_evolution
                        send_message_to_evolution.delay(str(confirmation_message.id))
                        logger.info(f"✅ [WELCOME MENU] Mensagem de confirmação de encerramento enfileirada")
                    except Exception as e:
                        logger.error(f"❌ [WELCOME MENU] Erro ao enfileirar confirmação: {e}", exc_info=True)
                
                transaction.on_commit(enqueue_confirmation)
                
                # ✅ Marcar todas as mensagens não lidas como lidas antes de fechar
                unread_messages = Message.objects.filter(
                    conversation=conversation,
                    direction='incoming',
                    status__in=['sent', 'delivered']  # Mensagens não lidas
                )
                
                marked_count = unread_messages.count()
                if marked_count > 0:
                    unread_messages.update(status='seen')
                    logger.info(f"✅ [WELCOME MENU] {marked_count} mensagens marcadas como lidas antes de fechar conversa {conversation.id}")
                
                # ✅ CORREÇÃO: Fechar conversa
                conversation.status = 'closed'
                conversation.save(update_fields=['status'])
                
                logger.info(f"✅ [WELCOME MENU] Conversa {conversation.id} fechada pelo cliente")
                return True
            
        except Exception as e:
            logger.error(f"❌ [WELCOME MENU] Erro ao fechar conversa: {e}", exc_info=True)
            return False
    
    @staticmethod
    def _send_invalid_option_message(conversation: Conversation, invalid_input: str, config: WelcomeMenuConfig) -> bool:
        """
        Envia mensagem avisando que a opção é inválida e reenvia o menu.
        
        Args:
            conversation: Conversa que recebeu opção inválida
            invalid_input: Texto/número inválido recebido
            config: Configuração do menu
        
        Returns:
            True se enviou com sucesso
        """
        try:
            # Mensagem de erro + menu novamente
            error_text = (
                f"❌ Opção *\"{invalid_input}\"* inválida.\n\n"
                f"Por favor, escolha uma das opções abaixo digitando *apenas o número*:\n\n"
            )
            
            # Adicionar opções do menu
            menu_text = config.get_menu_text()
            # Remover mensagem de boas-vindas (já foi enviada)
            menu_lines = menu_text.split('\n')
            # Pegar apenas as opções (linhas que começam com número)
            options_only = [line for line in menu_lines if line.strip() and (line[0].isdigit() or line.startswith('Escolha'))]
            
            full_message = error_text + '\n'.join(options_only)
            
            # Criar e enfileirar mensagem
            with transaction.atomic():
                message = Message.objects.create(
                    conversation=conversation,
                    sender=None,
                    content=full_message,
                    direction='outgoing',
                    status='pending',
                    is_internal=False,
                    metadata={
                        'welcome_menu_invalid_option': True,
                        'invalid_input': invalid_input,
                        'auto_sent': True
                    }
                )
                
                def enqueue_after_commit():
                    try:
                        from apps.chat.tasks import send_message_to_evolution
                        send_message_to_evolution.delay(str(message.id))
                        logger.info(f"✅ [WELCOME MENU] Mensagem de opção inválida enfileirada")
                    except Exception as e:
                        logger.error(f"❌ [WELCOME MENU] Erro ao enfileirar mensagem de erro: {e}", exc_info=True)
                
                transaction.on_commit(enqueue_after_commit)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [WELCOME MENU] Erro ao enviar mensagem de opção inválida: {e}", exc_info=True)
            return False
    
    @staticmethod
    def _send_inactivity_reminder(conversation: Conversation, config: WelcomeMenuConfig) -> bool:
        """
        Envia mensagem perguntando se cliente ainda está presente.
        
        Args:
            conversation: Conversa inativa
            config: Configuração do menu
        
        Returns:
            True se enviou com sucesso
        """
        try:
            remaining_minutes = config.auto_close_minutes - config.first_reminder_minutes
            
            reminder_text = (
                f"⏰ Você ainda está aí?\n\n"
                f"Digite *1* para continuar o atendimento ou aguarde que "
                f"encerraremos em *{remaining_minutes} minutos*."
            )
            
            # Criar e enfileirar mensagem
            with transaction.atomic():
                message = Message.objects.create(
                    conversation=conversation,
                    sender=None,
                    content=reminder_text,
                    direction='outgoing',
                    status='pending',
                    is_internal=False,
                    metadata={
                        'welcome_menu_reminder': True,
                        'auto_sent': True
                    }
                )
                
                def enqueue_after_commit():
                    try:
                        from apps.chat.tasks import send_message_to_evolution
                        send_message_to_evolution.delay(str(message.id))
                        logger.info(f"✅ [WELCOME MENU] Lembrete de inatividade enfileirado")
                    except Exception as e:
                        logger.error(f"❌ [WELCOME MENU] Erro ao enfileirar lembrete: {e}", exc_info=True)
                
                transaction.on_commit(enqueue_after_commit)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [WELCOME MENU] Erro ao enviar lembrete de inatividade: {e}", exc_info=True)
            return False

