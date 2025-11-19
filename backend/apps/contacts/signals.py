"""
Signals para atualizar métricas de contatos automaticamente e sincronizar com conversas
"""

from django.db.models.signals import post_save, post_delete, pre_save, m2m_changed
from django.dispatch import receiver
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


def get_contact_model():
    """Lazy import para evitar circular imports"""
    from apps.contacts.models import Contact
    return Contact


def normalize_phone_for_search(phone: str) -> str:
    """
    Normaliza telefone para busca (remove formatação, garante formato E.164).
    Usado para encontrar conversas mesmo com pequenas diferenças de formatação.
    """
    if not phone:
        return phone
    
    # Remover formatação (parênteses, hífens, espaços, @s.whatsapp.net)
    clean = phone.replace('@s.whatsapp.net', '').replace('@g.us', '')
    clean = ''.join(c for c in clean if c.isdigit() or c == '+')
    
    # Garantir formato E.164 (com +)
    if clean and not clean.startswith('+'):
        # Se começa com 55, adicionar +
        if clean.startswith('55'):
            clean = '+' + clean
        else:
            # Assumir Brasil (+55)
            clean = '+55' + clean
    
    return clean


@receiver(post_save)
def update_conversations_on_contact_change(sender, instance, created, **kwargs):
    """
    Quando um contato é criado ou atualizado:
    1. Invalidar cache de contact_tags nas conversas relacionadas
    2. Atualizar contact_name das conversas com o nome do contato
    3. Atualizar conversas relacionadas via WebSocket broadcast
    """
    # Verificar se é o modelo Contact
    Contact = get_contact_model()
    if not isinstance(instance, Contact):
        return
    
    from apps.chat.models import Conversation
    from apps.chat.utils.websocket import broadcast_conversation_updated
    
    # Invalidar cache de contact_tags para este contato
    # ✅ CORREÇÃO CRÍTICA: Normalizar telefone antes de invalidar cache
    # Isso garante que o cache seja invalidado mesmo se telefone estiver em formato diferente
    normalized_phone = normalize_phone_for_search(instance.phone)
    
    # Invalidar cache com telefone normalizado (formato usado no serializer)
    cache_key_normalized = f"contact_tags:{instance.tenant_id}:{normalized_phone}"
    cache.delete(cache_key_normalized)
    logger.info(f"🗑️ [CONTACT SIGNAL] Cache invalidado (normalizado): {cache_key_normalized}")
    
    # Também invalidar com telefone original (caso esteja em formato diferente)
    cache_key_original = f"contact_tags:{instance.tenant_id}:{instance.phone}"
    if cache_key_original != cache_key_normalized:
        cache.delete(cache_key_original)
        logger.info(f"🗑️ [CONTACT SIGNAL] Cache invalidado (original): {cache_key_original}")
    
    # Normalizar telefone do contato para busca
    normalized_contact_phone = normalize_phone_for_search(instance.phone)
    
    # Buscar todas as conversas relacionadas a este telefone no mesmo tenant
    # ✅ CORREÇÃO: Buscar por telefone normalizado para encontrar todas as variações
    conversations = Conversation.objects.filter(
        tenant=instance.tenant,
        conversation_type='individual'  # Apenas conversas individuais têm contatos
    )
    
    # Filtrar conversas que correspondem ao telefone (normalizando para comparação)
    matching_conversations = []
    for conv in conversations:
        normalized_conv_phone = normalize_phone_for_search(conv.contact_phone)
        if normalized_conv_phone == normalized_contact_phone:
            matching_conversations.append(conv)
    
    if matching_conversations:
        logger.info(f"🔄 [CONTACT SIGNAL] Atualizando {len(matching_conversations)} conversa(s) para contato {instance.phone}")
        
        # Atualizar cada conversa com nome do contato e fazer broadcast
        for conversation in matching_conversations:
            try:
                # ✅ CORREÇÃO CRÍTICA: Atualizar contact_name da conversa com nome do contato
                # Isso resolve o problema de conversas aparecendo com número ao invés do nome
                needs_update = False
                update_fields = []
                
                # Atualizar nome se diferente
                if conversation.contact_name != instance.name:
                    conversation.contact_name = instance.name
                    update_fields.append('contact_name')
                    needs_update = True
                    logger.info(f"📝 [CONTACT SIGNAL] Atualizando contact_name: '{conversation.contact_name}' → '{instance.name}'")
                
                # Se telefone da conversa está diferente (formatação), atualizar também
                if conversation.contact_phone != instance.phone:
                    conversation.contact_phone = instance.phone
                    update_fields.append('contact_phone')
                    needs_update = True
                    logger.info(f"📞 [CONTACT SIGNAL] Atualizando contact_phone: '{conversation.contact_phone}' → '{instance.phone}'")
                
                # Salvar se houver mudanças
                if needs_update:
                    conversation.save(update_fields=update_fields)
                    logger.info(f"✅ [CONTACT SIGNAL] Conversa {conversation.id} atualizada: {', '.join(update_fields)}")
                
                # Fazer broadcast da conversa atualizada (serializer vai buscar tags atualizadas)
                broadcast_conversation_updated(conversation)
                logger.debug(f"✅ [CONTACT SIGNAL] Broadcast enviado para conversa {conversation.id}")
            except Exception as e:
                logger.error(f"❌ [CONTACT SIGNAL] Erro ao fazer broadcast para conversa {conversation.id}: {e}", exc_info=True)
    else:
        logger.debug(f"ℹ️ [CONTACT SIGNAL] Nenhuma conversa encontrada para telefone {instance.phone} (normalizado: {normalized_contact_phone})")


@receiver(post_delete)
def update_conversations_on_contact_delete(sender, instance, **kwargs):
    """
    Quando um contato é deletado:
    1. Invalidar cache de contact_tags
    2. Atualizar conversas relacionadas (tags serão removidas automaticamente pelo serializer)
    """
    # Verificar se é o modelo Contact
    Contact = get_contact_model()
    if not isinstance(instance, Contact):
        return
    
    from apps.chat.models import Conversation
    from apps.chat.utils.websocket import broadcast_conversation_updated
    
    # Invalidar cache
    cache_key = f"contact_tags:{instance.tenant_id}:{instance.phone}"
    cache.delete(cache_key)
    logger.info(f"🗑️ [CONTACT SIGNAL] Cache invalidado após deleção: {cache_key}")
    
    # Buscar conversas relacionadas
    conversations = Conversation.objects.filter(
        tenant=instance.tenant,
        contact_phone=instance.phone,
        conversation_type='individual'
    )
    
    if conversations.exists():
        logger.info(f"🔄 [CONTACT SIGNAL] Atualizando {conversations.count()} conversa(s) após deleção do contato")
        
        for conversation in conversations:
            try:
                broadcast_conversation_updated(conversation)
                logger.debug(f"✅ [CONTACT SIGNAL] Broadcast enviado para conversa {conversation.id} após deleção")
            except Exception as e:
                logger.error(f"❌ [CONTACT SIGNAL] Erro ao fazer broadcast após deleção: {e}", exc_info=True)


# ==================== HISTÓRICO DE CONTATOS ====================

@receiver(post_save)
def create_chat_message_history(sender, instance, created, **kwargs):
    """
    Cria evento no histórico quando uma mensagem do chat é criada.
    """
    # Verificar se é o modelo Message do chat
    if sender.__name__ != 'Message' or not created:
        return
    
    # Verificar se é do app chat (não chat_messages)
    if not hasattr(instance, 'conversation'):
        return
    
    try:
        from apps.contacts.models import Contact, ContactHistory
        from apps.contacts.signals import normalize_phone_for_search
        from django.db.models import Q
        
        conversation = instance.conversation
        
        # Apenas para conversas individuais
        if conversation.conversation_type != 'individual':
            return
        
        # Buscar contato pelo telefone
        normalized_phone = normalize_phone_for_search(conversation.contact_phone)
        contact = Contact.objects.filter(
            Q(tenant=conversation.tenant) &
            (Q(phone=normalized_phone) | Q(phone=conversation.contact_phone))
        ).first()
        
        if not contact:
            return  # Contato não existe na lista
        
        # Criar evento no histórico
        ContactHistory.create_chat_message_event(
            contact=contact,
            tenant=conversation.tenant,
            message=instance,
            conversation=conversation,
            direction=instance.direction
        )
        
        logger.debug(f"✅ [HISTORY] Evento criado para mensagem {instance.id} do contato {contact.id}")
        
    except Exception as e:
        logger.error(f"❌ [HISTORY] Erro ao criar histórico de mensagem: {e}", exc_info=True)


# ✅ OTIMIZAÇÃO: Usar pre_save para capturar valores antigos
from django.db.models.signals import pre_save

def get_conversation_model():
    """Lazy import para evitar circular imports"""
    from apps.chat.models import Conversation
    return Conversation

@receiver(pre_save)
def capture_conversation_old_values(sender, instance, **kwargs):
    """Captura valores antigos antes de salvar para detectar mudanças"""
    Conversation = get_conversation_model()
    if sender != Conversation:
        return
    
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_department_id = old_instance.department_id
            instance._old_assigned_to_id = old_instance.assigned_to_id
            instance._old_assigned_to = old_instance.assigned_to
        except sender.DoesNotExist:
            instance._old_department_id = None
            instance._old_assigned_to_id = None
            instance._old_assigned_to = None
    else:
        instance._old_department_id = None
        instance._old_assigned_to_id = None
        instance._old_assigned_to = None


@receiver(post_save)
def create_conversation_transfer_history(sender, instance, created, **kwargs):
    """
    Cria evento no histórico quando uma conversa é transferida ou atribuída.
    ✅ OTIMIZADO: Usa valores capturados em pre_save
    """
    Conversation = get_conversation_model()
    if sender != Conversation:
        return
    
    # Apenas para conversas individuais
    if instance.conversation_type != 'individual':
        return
    
    try:
        from apps.contacts.models import Contact, ContactHistory
        from apps.contacts.signals import normalize_phone_for_search
        from django.db.models import Q
        
        # Buscar contato
        normalized_phone = normalize_phone_for_search(instance.contact_phone)
        contact = Contact.objects.filter(
            Q(tenant=instance.tenant) &
            (Q(phone=normalized_phone) | Q(phone=instance.contact_phone))
        ).first()
        
        if not contact:
            return
        
        # Verificar se houve mudança de departamento ou atribuição
        if created:
            # Nova conversa atribuída
            if instance.assigned_to:
                ContactHistory.objects.create(
                    contact=contact,
                    tenant=instance.tenant,
                    event_type='assigned_to',
                    title=f'Atribuído para {instance.assigned_to.get_full_name() or instance.assigned_to.email}',
                    description=f'Conversa atribuída para {instance.assigned_to.get_full_name() or instance.assigned_to.email}',
                    created_by=None,
                    is_editable=False,
                    metadata={
                        'assigned_to_id': str(instance.assigned_to.id),
                        'assigned_to_name': instance.assigned_to.get_full_name() or instance.assigned_to.email,
                    },
                    related_conversation=instance
                )
        else:
            # ✅ OTIMIZAÇÃO: Verificar mudanças usando valores capturados
            old_dept_id = getattr(instance, '_old_department_id', None)
            old_assigned_id = getattr(instance, '_old_assigned_to_id', None)
            
            if old_dept_id != instance.department_id:
                # Transferência de departamento
                from apps.authn.models import Department
                old_dept = Department.objects.filter(id=old_dept_id).first() if old_dept_id else None
                new_dept = instance.department
                
                ContactHistory.objects.create(
                    contact=contact,
                    tenant=instance.tenant,
                    event_type='department_transfer',
                    title=f'Transferido para {new_dept.name if new_dept else "Sem departamento"}',
                    description=f'Transferido de {old_dept.name if old_dept else "Sem departamento"} para {new_dept.name if new_dept else "Sem departamento"}',
                    created_by=None,
                    is_editable=False,
                    metadata={
                        'old_department_id': str(old_dept_id) if old_dept_id else None,
                        'new_department_id': str(instance.department_id) if instance.department_id else None,
                    },
                    related_conversation=instance
                )
            
            if old_assigned_id != (instance.assigned_to_id if instance.assigned_to_id else None):
                # Mudança de atribuição
                old_user = getattr(instance, '_old_assigned_to', None)
                new_user = instance.assigned_to
                
                ContactHistory.objects.create(
                    contact=contact,
                    tenant=instance.tenant,
                    event_type='assigned_to',
                    title=f'Atribuição alterada para {new_user.get_full_name() if new_user else "Ninguém"}',
                    description=f'Atribuição alterada de {old_user.get_full_name() if old_user else "Ninguém"} para {new_user.get_full_name() if new_user else "Ninguém"}',
                    created_by=None,
                    is_editable=False,
                    metadata={
                        'old_assigned_to_id': str(old_user.id) if old_user else None,
                        'new_assigned_to_id': str(new_user.id) if new_user else None,
                    },
                    related_conversation=instance
                )
        
    except Exception as e:
        logger.error(f"❌ [HISTORY] Erro ao criar histórico de transferência: {e}", exc_info=True)


# ==================== TAREFAS E HISTÓRICO ====================

@receiver(pre_save)
def capture_task_old_values(sender, instance, **kwargs):
    """Captura valores antigos da tarefa antes de salvar"""
    def get_task_model():
        from apps.contacts.models import Task
        return Task
    
    Task = get_task_model()
    if sender != Task:
        return
    
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
            instance._old_due_date = old_instance.due_date
        except sender.DoesNotExist:
            instance._old_status = None
            instance._old_due_date = None
    else:
        instance._old_status = None
        instance._old_due_date = None


@receiver(post_save)
def create_task_history_events(sender, instance, created, **kwargs):
    """
    Cria eventos no histórico de contatos quando tarefa é criada ou atualizada.
    """
    def get_task_model():
        from apps.contacts.models import Task
        return Task
    
    Task = get_task_model()
    if sender != Task:
        return
    
    try:
        from apps.contacts.models import ContactHistory
        
        # Se tarefa tem contatos relacionados, criar eventos no histórico
        if instance.related_contacts.exists():
            contacts = instance.related_contacts.all()
            
            if created:
                # Tarefa criada - criar evento para cada contato
                event_title = f"Tarefa criada: {instance.title}"
                if instance.due_date:
                    event_title += f" (Agendada para {instance.due_date.strftime('%d/%m/%Y às %H:%M')})"
                
                description_parts = []
                if instance.description:
                    description_parts.append(instance.description)
                if instance.assigned_to:
                    description_parts.append(f"Atribuída para: {instance.assigned_to.get_full_name() or instance.assigned_to.email}")
                
                for contact in contacts:
                    ContactHistory.objects.create(
                        contact=contact,
                        tenant=instance.tenant,
                        event_type='note',  # Usar 'note' pois é manual, mas poderia criar novo tipo
                        title=event_title,
                        description='\n'.join(description_parts) if description_parts else None,
                        created_by=instance.created_by,
                        is_editable=False,
                        metadata={
                            'task_id': str(instance.id),
                            'task_title': instance.title,
                            'task_status': instance.status,
                            'task_priority': instance.priority,
                            'due_date': instance.due_date.isoformat() if instance.due_date else None,
                            'assigned_to_id': str(instance.assigned_to.id) if instance.assigned_to else None,
                            'assigned_to_name': instance.assigned_to.get_full_name() if instance.assigned_to else None,
                            'department_id': str(instance.department.id),
                            'department_name': instance.department.name,
                        }
                    )
                
                logger.info(f"✅ [TASK HISTORY] Eventos criados no histórico para {contacts.count()} contato(s) - Tarefa: {instance.title}")
            
            elif not created:
                # Tarefa atualizada - verificar mudanças importantes
                old_status = getattr(instance, '_old_status', None)
                
                # Se status mudou para 'completed', criar evento de conclusão
                if old_status != 'completed' and instance.status == 'completed':
                    for contact in contacts:
                        ContactHistory.objects.create(
                            contact=contact,
                            tenant=instance.tenant,
                            event_type='note',
                            title=f"Tarefa concluída: {instance.title}",
                            description=f"Tarefa concluída por: {instance.assigned_to.get_full_name() if instance.assigned_to else 'Sistema'}",
                            created_by=instance.assigned_to,  # Quem concluiu (ou quem estava atribuído)
                            is_editable=False,
                            metadata={
                                'task_id': str(instance.id),
                                'task_title': instance.title,
                                'task_status': 'completed',
                                'completed_at': instance.completed_at.isoformat() if instance.completed_at else None,
                            }
                        )
                    
                    logger.info(f"✅ [TASK HISTORY] Eventos de conclusão criados para {contacts.count()} contato(s) - Tarefa: {instance.title}")
                
                # Se contatos foram adicionados depois, criar eventos retroativamente
                # (isso é tratado no m2m_changed signal abaixo)
    
    except Exception as e:
        logger.error(f"❌ [TASK HISTORY] Erro ao criar histórico de tarefa: {e}", exc_info=True)


@receiver(m2m_changed)
def handle_task_contacts_changed(sender, instance, action, pk_set, **kwargs):
    """
    Quando contatos são adicionados/removidos de uma tarefa existente.
    """
    # Verificar se é o relacionamento correto (Task.related_contacts)
    # O sender é a tabela intermediária, então verificamos pelo nome da tabela
    from apps.contacts.models import Task
    if not hasattr(sender, '_meta') or sender._meta.db_table != 'contacts_task_related_contacts':
        return
    
    # Verificar se a instância é uma Task
    if not isinstance(instance, Task):
        return
    
    if action == 'post_add':
        # Contatos foram adicionados - criar eventos no histórico
        try:
            from apps.contacts.models import ContactHistory, Contact
            
            if not instance.pk:
                return  # Tarefa ainda não foi salva
            
            contacts = Contact.objects.filter(pk__in=pk_set)
            
            for contact in contacts:
                # Verificar se já existe evento para esta tarefa
                existing = ContactHistory.objects.filter(
                    contact=contact,
                    tenant=instance.tenant,
                    metadata__task_id=str(instance.id)
                ).first()
                
                if not existing:
                    # Criar evento apenas se não existir
                    event_title = f"Tarefa relacionada: {instance.title}"
                    if instance.due_date:
                        event_title += f" (Agendada para {instance.due_date.strftime('%d/%m/%Y às %H:%M')})"
                    
                    description_parts = []
                    if instance.description:
                        description_parts.append(instance.description)
                    if instance.assigned_to:
                        description_parts.append(f"Atribuída para: {instance.assigned_to.get_full_name() or instance.assigned_to.email}")
                    
                    ContactHistory.objects.create(
                        contact=contact,
                        tenant=instance.tenant,
                        event_type='note',
                        title=event_title,
                        description='\n'.join(description_parts) if description_parts else None,
                        created_by=instance.created_by,
                        is_editable=False,
                        metadata={
                            'task_id': str(instance.id),
                            'task_title': instance.title,
                            'task_status': instance.status,
                            'task_priority': instance.priority,
                            'due_date': instance.due_date.isoformat() if instance.due_date else None,
                            'assigned_to_id': str(instance.assigned_to.id) if instance.assigned_to else None,
                            'assigned_to_name': instance.assigned_to.get_full_name() if instance.assigned_to else None,
                            'department_id': str(instance.department.id),
                            'department_name': instance.department.name,
                        }
                    )
            
            logger.info(f"✅ [TASK HISTORY] Eventos criados retroativamente para {contacts.count()} contato(s) adicionados à tarefa")
        
        except Exception as e:
            logger.error(f"❌ [TASK HISTORY] Erro ao criar histórico ao adicionar contatos: {e}", exc_info=True)
