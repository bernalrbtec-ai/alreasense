"""
Serviço para enviar notificações WhatsApp relacionadas a tarefas/agenda.
"""
import logging
from typing import Optional, List
from django.db import transaction, models
from django.utils import timezone
from zoneinfo import ZoneInfo
from datetime import datetime

from apps.contacts.models import Task, Contact
from apps.chat.models import Conversation, Message
from apps.chat.tasks import send_message_to_evolution
from apps.notifications.models import WhatsAppInstance
from apps.connections.models import EvolutionConnection

logger = logging.getLogger(__name__)


def send_task_notification_to_contacts(task: Task) -> List[str]:
    """
    Envia notificações WhatsApp para contatos relacionados quando notify_contacts está habilitado.
    
    Args:
        task: Tarefa com contatos relacionados
        
    Returns:
        Lista de IDs das mensagens criadas
    """
    if not task.related_contacts.exists():
        logger.debug(f"ℹ️ [TASK NOTIFICATION] Tarefa {task.id} não tem contatos relacionados")
        return []
    
    # Verificar se notify_contacts está habilitado no metadata
    metadata = task.metadata or {}
    notify_contacts = metadata.get('notify_contacts', False)
    
    if not notify_contacts:
        logger.debug(f"ℹ️ [TASK NOTIFICATION] notify_contacts está desabilitado para tarefa {task.id}")
        return []
    
    # Verificar se tarefa tem data agendada
    if not task.due_date:
        logger.debug(f"ℹ️ [TASK NOTIFICATION] Tarefa {task.id} não tem data agendada")
        return []
    
    # Buscar instância WhatsApp ativa
    instance = WhatsAppInstance.objects.filter(
        tenant=task.tenant,
        is_active=True,
        status='active'
    ).first()
    
    if not instance:
        logger.warning(f"⚠️ [TASK NOTIFICATION] Nenhuma instância WhatsApp ativa para tenant {task.tenant.name}")
        return []
    
    # Buscar conexão Evolution
    connection = EvolutionConnection.objects.filter(is_active=True).first()
    
    if not connection and not instance.api_url:
        logger.warning(f"⚠️ [TASK NOTIFICATION] Configuração da Evolution API não encontrada")
        return []
    
    message_ids = []
    contacts = task.related_contacts.all()
    
    # Formatar data/hora
    due_date_local = task.due_date.astimezone(ZoneInfo('America/Sao_Paulo'))
    due_date_str = due_date_local.strftime('%d/%m/%Y às %H:%M')
    
    # Criar mensagem para cada contato
    for contact in contacts:
        try:
            # Normalizar telefone do contato
            phone = contact.phone
            if not phone:
                logger.warning(f"⚠️ [TASK NOTIFICATION] Contato {contact.id} não tem telefone")
                continue
            
            # Garantir formato E.164
            if not phone.startswith('+'):
                if phone.startswith('55'):
                    phone = '+' + phone
                else:
                    phone = '+55' + phone
            
            # Buscar ou criar conversa
            conversation = get_or_create_conversation(
                tenant=task.tenant,
                contact_phone=phone,
                contact_name=contact.name,
                instance=instance
            )
            
            if not conversation:
                logger.warning(f"⚠️ [TASK NOTIFICATION] Não foi possível criar/buscar conversa para {phone}")
                continue
            
            # Criar mensagem de notificação
            message_content = format_task_notification_message(task, due_date_str)
            
            message = Message.objects.create(
                conversation=conversation,
                content=message_content,
                direction='outgoing',
                status='pending',
                is_internal=False,
                metadata={
                    'is_task_notification': True,
                    'task_id': str(task.id),
                    'task_title': task.title,
                    'due_date': task.due_date.isoformat() if task.due_date else None,
                }
            )
            
            # Enfileirar para envio
            send_message_to_evolution.delay(str(message.id))
            message_ids.append(str(message.id))
            
            logger.info(f"✅ [TASK NOTIFICATION] Mensagem criada e enfileirada para contato {contact.name} ({phone})")
            
        except Exception as e:
            logger.error(f"❌ [TASK NOTIFICATION] Erro ao enviar notificação para contato {contact.id}: {e}", exc_info=True)
            continue
    
    return message_ids


def get_or_create_conversation(
    tenant,
    contact_phone: str,
    contact_name: str,
    instance: WhatsAppInstance
) -> Optional[Conversation]:
    """
    Busca ou cria conversa para um contato.
    
    Args:
        tenant: Tenant da conversa
        contact_phone: Telefone do contato (formato E.164)
        contact_name: Nome do contato
        instance: Instância WhatsApp
        
    Returns:
        Conversation ou None se erro
    """
    try:
        # Normalizar telefone para busca
        phone_normalized = contact_phone.replace('+', '').strip()
        phone_with_suffix = f"{phone_normalized}@s.whatsapp.net"
        
        # Buscar conversa existente
        conversation = Conversation.objects.filter(
            tenant=tenant,
            contact_phone__in=[contact_phone, phone_with_suffix, phone_normalized],
            conversation_type='individual'
        ).first()
        
        if conversation:
            # Atualizar nome se necessário
            if conversation.contact_name != contact_name:
                conversation.contact_name = contact_name
                conversation.save(update_fields=['contact_name'])
            return conversation
        
        # Criar nova conversa
        conversation = Conversation.objects.create(
            tenant=tenant,
            contact_phone=phone_with_suffix,  # Formato padrão: número@s.whatsapp.net
            contact_name=contact_name,
            conversation_type='individual',
            status='pending',  # Inbox
            department=None,  # Sem departamento = Inbox
            metadata={
                'created_from_task': True,
                'instance_name': instance.instance_name if instance else None
            }
        )
        
        logger.info(f"✅ [TASK NOTIFICATION] Conversa criada: {conversation.id} para {contact_name} ({phone_with_suffix})")
        return conversation
        
    except Exception as e:
        logger.error(f"❌ [TASK NOTIFICATION] Erro ao criar/buscar conversa: {e}", exc_info=True)
        return None


def format_task_notification_message(task: Task, due_date_str: str) -> str:
    """
    Formata mensagem de notificação de tarefa.
    
    Args:
        task: Tarefa
        due_date_str: Data/hora formatada
        
    Returns:
        Mensagem formatada
    """
    message_parts = []
    
    # Título
    if task.task_type == 'agenda':
        message_parts.append("📅 *Compromisso Agendado*")
    else:
        message_parts.append("📋 *Tarefa Criada*")
    
    message_parts.append("")  # Linha em branco
    
    # Título da tarefa
    message_parts.append(f"*{task.title}*")
    message_parts.append("")  # Linha em branco
    
    # Descrição (se houver)
    if task.description:
        desc = task.description[:300].replace('\n', ' ')
        message_parts.append(desc)
        message_parts.append("")  # Linha em branco
    
    # Data/hora
    message_parts.append(f"📅 *Data/Hora:* {due_date_str}")
    
    # Departamento (se houver)
    if task.department:
        message_parts.append(f"🏢 *Departamento:* {task.department.name}")
    
    # Responsável (se houver)
    if task.assigned_to:
        assigned_name = task.assigned_to.get_full_name() or task.assigned_to.email
        message_parts.append(f"👤 *Responsável:* {assigned_name}")
    
    message_parts.append("")  # Linha em branco
    message_parts.append("Você receberá um lembrete 15 minutos antes do compromisso.")
    
    return "\n".join(message_parts)


def send_task_reminder_to_contacts(task: Task, is_15min_before: bool = True) -> List[str]:
    """
    Envia lembrete de tarefa para contatos relacionados.
    
    Args:
        task: Tarefa
        is_15min_before: Se True, é lembrete 15min antes. Se False, é no momento exato.
        
    Returns:
        Lista de IDs das mensagens criadas
    """
    if not task.related_contacts.exists():
        return []
    
    # Verificar se notify_contacts está habilitado
    metadata = task.metadata or {}
    notify_contacts = metadata.get('notify_contacts', False)
    
    if not notify_contacts:
        return []
    
    # Buscar instância WhatsApp
    instance = WhatsAppInstance.objects.filter(
        tenant=task.tenant,
        is_active=True,
        status='active'
    ).first()
    
    if not instance:
        return []
    
    message_ids = []
    contacts = task.related_contacts.all()
    
    # Formatar data/hora
    due_date_local = task.due_date.astimezone(ZoneInfo('America/Sao_Paulo'))
    due_date_str = due_date_local.strftime('%d/%m/%Y às %H:%M')
    
    # Criar mensagem de lembrete
    if is_15min_before:
        reminder_text = "🔔 *Lembrete de Compromisso*\n\n"
        reminder_text += f"Você tem um compromisso em 15 minutos:\n\n"
    else:
        reminder_text = "⏰ *Compromisso Agendado*\n\n"
        reminder_text += f"Seu compromisso é agora:\n\n"
    
    reminder_text += f"*{task.title}*\n"
    reminder_text += f"📅 {due_date_str}\n"
    
    if task.description:
        desc = task.description[:200].replace('\n', ' ')
        reminder_text += f"\n{desc}"
    
    # Enviar para cada contato
    for contact in contacts:
        try:
            phone = contact.phone
            if not phone:
                continue
            
            # Normalizar telefone
            if not phone.startswith('+'):
                if phone.startswith('55'):
                    phone = '+' + phone
                else:
                    phone = '+55' + phone
            
            # Buscar conversa
            conversation = get_or_create_conversation(
                tenant=task.tenant,
                contact_phone=phone,
                contact_name=contact.name,
                instance=instance
            )
            
            if not conversation:
                continue
            
            # Criar mensagem
            message = Message.objects.create(
                conversation=conversation,
                content=reminder_text,
                direction='outgoing',
                status='pending',
                is_internal=False,
                metadata={
                    'is_task_reminder': True,
                    'task_id': str(task.id),
                    'is_15min_before': is_15min_before,
                }
            )
            
            # Enfileirar para envio
            send_message_to_evolution.delay(str(message.id))
            message_ids.append(str(message.id))
            
        except Exception as e:
            logger.error(f"❌ [TASK REMINDER] Erro ao enviar lembrete para contato {contact.id}: {e}", exc_info=True)
            continue
    
    return message_ids

