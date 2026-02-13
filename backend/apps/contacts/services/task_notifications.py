"""
Serviço para enviar notificações WhatsApp relacionadas a tarefas/agenda.
"""
import logging
from typing import Optional, List
from django.db import transaction, models, IntegrityError
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

    contact_phone pode ser E.164 ou outro formato (ex.: com @s.whatsapp.net) e será
    normalizado internamente. Novas conversas são criadas com contact_phone em formato
    E.164 (canônico).

    Args:
        tenant: Tenant da conversa
        contact_phone: Telefone do contato (E.164 ou outro formato; será normalizado)
        contact_name: Nome do contato
        instance: Instância WhatsApp

    Returns:
        Conversation ou None se erro
    """
    try:
        # 3.1 / 3.2 – Guarda inicial
        if contact_phone is None or (isinstance(contact_phone, str) and not contact_phone.strip()):
            logger.warning("⚠️ [TASK NOTIFICATION] get_or_create_conversation chamado sem contact_phone")
            return None

        if not isinstance(contact_phone, str):
            contact_phone = str(contact_phone)

        from apps.contacts.signals import normalize_phone_for_search

        canonical_phone = normalize_phone_for_search(contact_phone)
        if not canonical_phone or (isinstance(canonical_phone, str) and not canonical_phone.strip()):
            canonical_phone = contact_phone
        if not canonical_phone or (isinstance(canonical_phone, str) and not canonical_phone.strip()):
            logger.warning("⚠️ [TASK NOTIFICATION] contact_phone inválido após normalização")
            return None

        # 3.3 – Cálculo para busca (formatos antigos)
        phone_normalized = contact_phone.replace('+', '').strip()
        phone_with_suffix = f"{phone_normalized}@s.whatsapp.net"

        candidate_list = [
            canonical_phone,
            phone_with_suffix,
            phone_normalized,
            contact_phone,
        ]
        candidate_list = [p for p in candidate_list if p is not None and (not isinstance(p, str) or p.strip())]
        if not candidate_list:
            logger.warning("⚠️ [TASK NOTIFICATION] Lista de candidatos vazia para busca de conversa")
            return None

        conversation = Conversation.objects.filter(
            tenant=tenant,
            contact_phone__in=candidate_list,
            conversation_type='individual'
        ).first()

        if conversation:
            # 3.4 – Atualizar nome e opcionalmente telefone (só se @s.whatsapp.net e sem duplicata)
            update_fields = []
            name_value = contact_name or ''
            if conversation.contact_name != name_value:
                conversation.contact_name = name_value
                update_fields.append('contact_name')
            if '@s.whatsapp.net' in (conversation.contact_phone or ''):
                other_exists = Conversation.objects.filter(
                    tenant=tenant,
                    contact_phone=canonical_phone
                ).exclude(id=conversation.id).exists()
                if not other_exists:
                    conversation.contact_phone = canonical_phone
                    update_fields.append('contact_phone')
            if update_fields:
                conversation.save(update_fields=update_fields)
            return conversation

        # 3.5 – Criar nova conversa (com tratamento de race)
        try:
            conversation = Conversation.objects.create(
                tenant=tenant,
                contact_phone=canonical_phone,
                contact_name=contact_name or '',
                conversation_type='individual',
                status='pending',
                department=None,
                metadata={
                    'created_from_task': True,
                    'instance_name': instance.instance_name if instance else None
                }
            )
        except IntegrityError as create_err:
            if 'idx_chat_conversation_unique' in str(create_err):
                conversation = Conversation.objects.filter(
                    tenant=tenant,
                    contact_phone__in=candidate_list,
                    conversation_type='individual'
                ).first()
                if conversation:
                    logger.info(
                        "ℹ️ [TASK NOTIFICATION] Conversa encontrada após race na criação (%s)",
                        canonical_phone
                    )
                    return conversation
            raise

        logger.info(
            "✅ [TASK NOTIFICATION] Conversa criada: %s para %s (%s)",
            conversation.id,
            contact_name,
            canonical_phone
        )
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


def send_daily_summary_to_user(user, date=None, include_department_tasks=True, use_preferences=True) -> Optional[str]:
    """
    Envia resumo diário de tarefas/compromissos para um usuário.
    
    ✅ UNIFICADO: Integra funcionalidade existente com melhorias de UX.
    
    Args:
        user: Usuário para enviar resumo
        date: Data do resumo (padrão: hoje)
        include_department_tasks: Se True, inclui tarefas do departamento do usuário
        use_preferences: Se True, verifica preferências do usuário antes de enviar
        
    Returns:
        ID da mensagem criada ou None se erro
    """
    from apps.notifications.models import UserNotificationPreferences
    from apps.notifications.services import get_greeting, format_weekday_pt
    
    # ✅ CORREÇÃO: Definir timezone UTC-3 explicitamente
    sao_paulo_tz = ZoneInfo('America/Sao_Paulo')
    
    # Verificar preferências se solicitado
    if use_preferences:
        try:
            pref = UserNotificationPreferences.objects.filter(
                user=user,
                tenant=user.tenant
            ).first()
            
            if not pref or not pref.daily_summary_enabled:
                logger.debug(f"ℹ️ [DAILY SUMMARY] Resumo diário desabilitado para {user.email}")
                return None
            
            # ✅ CORREÇÃO: Verificar se já foi enviado hoje usando UTC-3
            if date is None:
                now_local = timezone.now().astimezone(sao_paulo_tz)
                date = now_local.date()
            
            if pref.last_daily_summary_sent_date == date:
                logger.debug(f"ℹ️ [DAILY SUMMARY] Resumo já enviado hoje para {user.email}")
                return None
        except Exception as e:
            logger.warning(f"⚠️ [DAILY SUMMARY] Erro ao verificar preferências: {e}")
    
    if not user.phone:
        logger.debug(f"ℹ️ [DAILY SUMMARY] Usuário {user.email} não tem telefone")
        return None
    
    # Buscar instância WhatsApp
    instance = WhatsAppInstance.objects.filter(
        tenant=user.tenant,
        is_active=True,
        status='active'
    ).first()
    
    if not instance:
        logger.warning(f"⚠️ [DAILY SUMMARY] Nenhuma instância WhatsApp ativa para tenant {user.tenant.name}")
        return None
    
    # Data do resumo (hoje por padrão) - usar timezone local (UTC-3)
    if date is None:
        now_local = timezone.now().astimezone(sao_paulo_tz)
        date = now_local.date()
    
    # Buscar tarefas do dia usando UTC-3
    # Criar datetime início e fim do dia em UTC-3
    date_start_local = datetime.combine(date, datetime.min.time())
    date_end_local = datetime.combine(date, datetime.max.time())
    
    # Converter para timezone-aware em UTC-3
    date_start = sao_paulo_tz.localize(date_start_local)
    date_end = sao_paulo_tz.localize(date_end_local)
    
    logger.debug(f"🔍 [DAILY SUMMARY] Buscando tarefas de {date_start.strftime('%Y-%m-%d %H:%M:%S %Z')} até {date_end.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Buscar tarefas atribuídas ao usuário
    tasks_assigned = Task.objects.filter(
        tenant=user.tenant,
        assigned_to=user,
        due_date__gte=date_start,
        due_date__lte=date_end,
        status__in=['pending', 'in_progress']
    ).select_related('department', 'assigned_to').order_by('due_date')
    
    # Buscar tarefas do departamento (se habilitado)
    tasks_department = Task.objects.none()
    if include_department_tasks:
        user_departments = user.departments.all()
        if user_departments.exists():
            tasks_department = Task.objects.filter(
                tenant=user.tenant,
                department__in=user_departments,
                due_date__gte=date_start,
                due_date__lte=date_end,
                status__in=['pending', 'in_progress']
            ).exclude(assigned_to=user).select_related('department', 'assigned_to').order_by('due_date')
    
    # Combinar tarefas (remover duplicatas)
    all_tasks = list(tasks_assigned) + list(tasks_department)
    unique_tasks = {task.id: task for task in all_tasks}.values()
    tasks = sorted(unique_tasks, key=lambda t: t.due_date)
    
    # ✅ CORREÇÃO: Buscar tarefas atrasadas usando UTC-3
    now_local = timezone.now().astimezone(sao_paulo_tz)
    tasks_overdue = Task.objects.filter(
        tenant=user.tenant,
        assigned_to=user,
        due_date__lt=now_local,
        status__in=['pending', 'in_progress']
    ).count()
    
    # Preparar dados para formatação
    tasks_pending = [t for t in tasks if t.status == 'pending']
    tasks_in_progress = [t for t in tasks if t.status == 'in_progress']
    
    # Formatar mensagem melhorada (UX unificada)
    greeting = get_greeting()
    weekday = format_weekday_pt(date)
    date_str = date.strftime('%d/%m/%Y')
    
    message_parts = []
    
    # Saudação personalizada
    user_name = user.first_name or user.email.split('@')[0]
    message_parts.append(f"{greeting}, {user_name}!\n")
    
    # Cabeçalho
    message_parts.append(f"📅 *Resumo do Dia - {weekday}*\n")
    message_parts.append(f"📆 {date_str}\n")
    message_parts.append("")  # Linha em branco
    
    # Resumo com contadores (melhor UX)
    if tasks_pending or tasks_in_progress or tasks_overdue > 0:
        message_parts.append("📋 *Resumo de Tarefas:*\n")
        if tasks_pending:
            message_parts.append(f"   ⏰ Pendentes: {len(tasks_pending)}")
        if tasks_in_progress:
            message_parts.append(f"   🔄 Em progresso: {len(tasks_in_progress)}")
        if tasks_overdue > 0:
            message_parts.append(f"   ⚠️ Atrasadas: {tasks_overdue}")
        message_parts.append("")  # Linha em branco
        
        # Lista detalhada de tarefas (melhor UX)
        if tasks:
            message_parts.append("📝 *Compromissos de Hoje:*\n")
            for task in tasks:
                # ✅ CORREÇÃO: Converter para UTC-3 explicitamente
                task_due_local = task.due_date.astimezone(sao_paulo_tz)
                due_time = task_due_local.strftime('%H:%M')
                status_emoji = "⏰" if task.status == 'pending' else "🔄"
                
                # ✅ CORREÇÃO: Verificar se está atrasada usando UTC-3
                if task_due_local < now_local:
                    status_emoji = "⚠️"
                
                message_parts.append(f"{status_emoji} *{due_time}* - {task.title}")
                
                # Adicionar informações extras
                info_parts = []
                if task.department:
                    info_parts.append(f"🏢 {task.department.name}")
                if task.assigned_to != user:
                    assigned_name = task.assigned_to.get_full_name() if task.assigned_to else "Não atribuído"
                    info_parts.append(f"👤 {assigned_name}")
                
                if info_parts:
                    message_parts.append(f"   {' | '.join(info_parts)}")
                
                message_parts.append("")  # Linha em branco
    else:
        message_parts.append("✅ Nenhuma tarefa agendada para hoje!\n")
        message_parts.append("")  # Linha em branco
    
    # Mensagem de despedida
    message_parts.append("Tenha um ótimo dia! 🚀")
    
    message_content = "\n".join(message_parts)
    
    # Buscar ou criar conversa
    phone = user.phone
    if not phone.startswith('+'):
        if phone.startswith('55'):
            phone = '+' + phone
        else:
            phone = '+55' + phone
    
    conversation = get_or_create_conversation(
        tenant=user.tenant,
        contact_phone=phone,
        contact_name=user.get_full_name() or user.email,
        instance=instance
    )
    
    if not conversation:
        return None
    
    # Criar mensagem
    message = Message.objects.create(
        conversation=conversation,
        content=message_content,
        direction='outgoing',
        status='pending',
        is_internal=False,
        metadata={
            'is_daily_summary': True,
            'summary_date': date.isoformat(),
            'tasks_count': len(tasks),
            'tasks_pending': len(tasks_pending),
            'tasks_in_progress': len(tasks_in_progress),
            'tasks_overdue': tasks_overdue,
            'include_department_tasks': include_department_tasks,
        }
    )
    
    # Enfileirar para envio
    send_message_to_evolution.delay(str(message.id))
    
    # Atualizar preferências se necessário
    if use_preferences:
        try:
            pref = UserNotificationPreferences.objects.filter(
                user=user,
                tenant=user.tenant
            ).first()
            if pref:
                pref.last_daily_summary_sent_date = date
                pref.save(update_fields=['last_daily_summary_sent_date'])
        except Exception as e:
            logger.warning(f"⚠️ [DAILY SUMMARY] Erro ao atualizar preferências: {e}")
    
    logger.info(f"✅ [DAILY SUMMARY] Resumo diário criado e enfileirado para {user.email} ({len(tasks)} tarefas)")
    
    return str(message.id)


def send_department_summary_to_users(department, date=None) -> List[str]:
    """
    Envia resumo de tarefas/compromissos do departamento para todos os usuários do departamento.
    
    Args:
        department: Departamento
        date: Data do resumo (padrão: hoje)
        
    Returns:
        Lista de IDs das mensagens criadas
    """
    from apps.authn.models import User
    
    message_ids = []
    
    # Buscar usuários do departamento que têm telefone
    users = User.objects.filter(
        tenant=department.tenant,
        departments=department,
        phone__isnull=False
    ).exclude(phone='')
    
    for user in users:
        try:
            # Enviar resumo diário para cada usuário
            message_id = send_daily_summary_to_user(user, date)
            if message_id:
                message_ids.append(message_id)
        except Exception as e:
            logger.error(f"❌ [DEPARTMENT SUMMARY] Erro ao enviar resumo para {user.email}: {e}", exc_info=True)
            continue
    
    return message_ids

