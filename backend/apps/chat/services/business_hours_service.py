"""
Serviço para verificação de horários de atendimento e criação de tarefas automáticas.
"""
import logging
from datetime import datetime, time, timedelta
from typing import Optional, Tuple, Dict, Any
from zoneinfo import ZoneInfo
from django.utils import timezone as django_timezone
from django.db import transaction
from django.db.models import Q

from apps.chat.models_business_hours import (
    BusinessHours,
    AfterHoursMessage,
    AfterHoursTaskConfig
)
from apps.chat.models import Conversation, Message
from apps.contacts.models import Task, Contact

logger = logging.getLogger(__name__)


class BusinessHoursService:
    """Serviço para gerenciar horários de atendimento."""
    
    @staticmethod
    def get_business_hours(tenant, department=None) -> Optional[BusinessHours]:
        """
        Busca horários de atendimento.
        
        Prioridade:
        1. Horário específico do departamento (se department fornecido)
        2. Horário geral do tenant
        3. None (sem horário configurado)
        """
        if department:
            # Tenta buscar horário específico do departamento
            business_hours = BusinessHours.objects.filter(
                tenant=tenant,
                department=department,
                is_active=True
            ).first()
            
            if business_hours:
                return business_hours
        
        # Busca horário geral do tenant
        business_hours = BusinessHours.objects.filter(
            tenant=tenant,
            department__isnull=True,
            is_active=True
        ).first()
        
        return business_hours
    
    @staticmethod
    def is_business_hours(tenant, department=None, check_datetime: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
        """
        Verifica se está dentro do horário de atendimento.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_open, next_open_time)
            - is_open: True se está dentro do horário
            - next_open_time: String formatada com próximo horário de abertura (se fechado)
        """
        business_hours = BusinessHoursService.get_business_hours(tenant, department)
        
        if not business_hours:
            # Sem horário configurado = sempre aberto
            logger.info(f"⏰ [BUSINESS HOURS] Nenhum horário configurado para tenant={tenant.name}, department={department.name if department else 'None'} - considerando sempre aberto")
            return True, None
        
        logger.info(f"⏰ [BUSINESS HOURS] Verificando horário: tenant={tenant.name}, department={department.name if department else 'None'}, config_id={business_hours.id}")
        
        # Usa datetime fornecido ou agora
        if check_datetime is None:
            check_datetime = django_timezone.now()
        
        # Converte para timezone configurado
        tz = ZoneInfo(business_hours.timezone)
        local_datetime = check_datetime.astimezone(tz)
        local_date = local_datetime.date()
        local_time = local_datetime.time()
        weekday = local_datetime.weekday()  # 0=Monday, 6=Sunday
        
        logger.info(f"⏰ [BUSINESS HOURS] Data/hora local: {local_datetime.strftime('%Y-%m-%d %H:%M:%S')} (timezone: {business_hours.timezone})")
        logger.info(f"⏰ [BUSINESS HOURS] Dia da semana: {weekday} (0=Segunda, 6=Domingo)")
        
        # Verifica se é feriado
        holidays = business_hours.holidays or []
        date_str = local_date.strftime('%Y-%m-%d')
        if date_str in holidays:
            # É feriado = fechado
            logger.info(f"⏰ [BUSINESS HOURS] É feriado ({date_str}) - fechado")
            next_open = BusinessHoursService._get_next_open_time(business_hours, local_datetime)
            return False, next_open
        
        # Mapeia weekday para campos do modelo
        day_configs = {
            0: ('monday_enabled', 'monday_start', 'monday_end', 'Segunda-feira'),    # Segunda
            1: ('tuesday_enabled', 'tuesday_start', 'tuesday_end', 'Terça-feira'),  # Terça
            2: ('wednesday_enabled', 'wednesday_start', 'wednesday_end', 'Quarta-feira'),  # Quarta
            3: ('thursday_enabled', 'thursday_start', 'thursday_end', 'Quinta-feira'),  # Quinta
            4: ('friday_enabled', 'friday_start', 'friday_end', 'Sexta-feira'),    # Sexta
            5: ('saturday_enabled', 'saturday_start', 'saturday_end', 'Sábado'),  # Sábado
            6: ('sunday_enabled', 'sunday_start', 'sunday_end', 'Domingo'),   # Domingo
        }
        
        enabled_field, start_field, end_field, day_name = day_configs[weekday]
        is_enabled = getattr(business_hours, enabled_field)
        start_time = getattr(business_hours, start_field)
        end_time = getattr(business_hours, end_field)
        
        logger.info(f"⏰ [BUSINESS HOURS] {day_name}: enabled={is_enabled}, horário={start_time} - {end_time}, hora atual={local_time}")
        
        if not is_enabled:
            # Dia desabilitado = fechado
            logger.info(f"⏰ [BUSINESS HOURS] {day_name} está desabilitado - fechado")
            next_open = BusinessHoursService._get_next_open_time(business_hours, local_datetime)
            return False, next_open
        
        # Verifica se está dentro do horário
        if start_time <= local_time <= end_time:
            logger.info(f"⏰ [BUSINESS HOURS] Dentro do horário de atendimento ({start_time} <= {local_time} <= {end_time})")
            return True, None
        
        # Fora do horário
        logger.info(f"⏰ [BUSINESS HOURS] Fora do horário de atendimento ({local_time} não está entre {start_time} e {end_time})")
        next_open = BusinessHoursService._get_next_open_time(business_hours, local_datetime)
        return False, next_open
    
    @staticmethod
    def _get_next_open_time(business_hours: BusinessHours, current_datetime: datetime) -> str:
        """
        Calcula o próximo horário de abertura.
        
        Returns:
            str: Próximo horário formatado (ex: "Segunda-feira, 09:00")
        """
        tz = ZoneInfo(business_hours.timezone)
        local_datetime = current_datetime.astimezone(tz)
        
        # Procura nos próximos 7 dias
        for days_ahead in range(1, 8):
            check_date = local_datetime.date() + timedelta(days=days_ahead)
            check_weekday = check_date.weekday()
            
            # Verifica se é feriado
            holidays = business_hours.holidays or []
            date_str = check_date.strftime('%Y-%m-%d')
            if date_str in holidays:
                continue
            
            # Mapeia weekday para campos
            day_configs = {
                0: ('monday_enabled', 'monday_start', 'Segunda-feira'),
                1: ('tuesday_enabled', 'tuesday_start', 'Terça-feira'),
                2: ('wednesday_enabled', 'wednesday_start', 'Quarta-feira'),
                3: ('thursday_enabled', 'thursday_start', 'Quinta-feira'),
                4: ('friday_enabled', 'friday_start', 'Sexta-feira'),
                5: ('saturday_enabled', 'saturday_start', 'Sábado'),
                6: ('sunday_enabled', 'sunday_start', 'Domingo'),
            }
            
            enabled_field, start_field, day_name = day_configs[check_weekday]
            is_enabled = getattr(business_hours, enabled_field)
            start_time = getattr(business_hours, start_field)
            
            if is_enabled:
                # Formata: "Segunda-feira, 09:00"
                time_str = start_time.strftime('%H:%M')
                return f"{day_name}, {time_str}"
        
        return "Em breve"
    
    @staticmethod
    def get_after_hours_message(tenant, department=None) -> Optional[AfterHoursMessage]:
        """Busca mensagem automática para fora de horário."""
        if department:
            message = AfterHoursMessage.objects.filter(
                tenant=tenant,
                department=department,
                is_active=True
            ).first()
            if message:
                return message
        
        # Busca mensagem geral do tenant
        message = AfterHoursMessage.objects.filter(
            tenant=tenant,
            department__isnull=True,
            is_active=True
        ).first()
        
        return message
    
    @staticmethod
    def get_after_hours_task_config(tenant, department=None) -> Optional[AfterHoursTaskConfig]:
        """Busca configuração de tarefa automática."""
        logger.info(f"🔍 [BUSINESS HOURS TASK] Buscando configuração de tarefa...")
        logger.info(f"   Tenant: {tenant.name} (ID: {tenant.id})")
        logger.info(f"   Department: {department.name if department else 'None'}")
        
        if department:
            config = AfterHoursTaskConfig.objects.filter(
                tenant=tenant,
                department=department,
                is_active=True
            ).first()
            if config:
                logger.info(f"✅ [BUSINESS HOURS TASK] Configuração específica do departamento encontrada: ID={config.id}")
                return config
            else:
                logger.info(f"ℹ️ [BUSINESS HOURS TASK] Nenhuma configuração específica do departamento encontrada")
        
        # Busca configuração geral do tenant
        config = AfterHoursTaskConfig.objects.filter(
            tenant=tenant,
            department__isnull=True,
            is_active=True
        ).first()
        
        if config:
            logger.info(f"✅ [BUSINESS HOURS TASK] Configuração geral do tenant encontrada: ID={config.id}")
        else:
            logger.warning(f"⚠️ [BUSINESS HOURS TASK] Nenhuma configuração encontrada (nem específica nem geral)")
            # Log adicional para debug: verificar se existe configuração inativa
            if department:
                inactive_dept = AfterHoursTaskConfig.objects.filter(
                    tenant=tenant,
                    department=department,
                    is_active=False
                ).count()
                if inactive_dept > 0:
                    logger.warning(f"⚠️ [BUSINESS HOURS TASK] Existe configuração do departamento '{department.name}' mas está INATIVA (is_active=False)")
            
            inactive_general = AfterHoursTaskConfig.objects.filter(
                tenant=tenant,
                department__isnull=True,
                is_active=False
            ).count()
            if inactive_general > 0:
                logger.warning(f"⚠️ [BUSINESS HOURS TASK] Existe configuração geral do tenant mas está INATIVA (is_active=False)")
        
        return config
    
    @staticmethod
    def format_message_template(template: str, context: Dict[str, Any]) -> str:
        """
        Formata template de mensagem com variáveis.
        
        Variáveis disponíveis:
        - {contact_name}: Nome do contato
        - {department_name}: Nome do departamento
        - {next_open_time}: Próximo horário de abertura
        - {message_time}: Horário da mensagem
        - {message_content}: Conteúdo da mensagem (primeiras 100 chars)
        - {contact_phone}: Telefone do contato
        """
        try:
            return template.format(**context)
        except KeyError as e:
            logger.warning(f"Variável não encontrada no template: {e}")
            return template
    
    @staticmethod
    @transaction.atomic
    def handle_after_hours_message(
        conversation: Conversation,
        message: Message,
        tenant,
        department=None
    ) -> Tuple[bool, Optional[Message]]:
        """
        Processa mensagem recebida fora de horário.
        
        Returns:
            Tuple[bool, Optional[Message]]: (was_after_hours, auto_message_sent)
            - was_after_hours: True se estava fora de horário
            - auto_message_sent: Mensagem automática enviada (se houver)
        """
        # Verifica se está fora de horário
        is_open, next_open_time = BusinessHoursService.is_business_hours(
            tenant, department, message.created_at
        )
        
        if is_open:
            # Dentro do horário = não faz nada
            return False, None
        
        # Fora de horário - busca mensagem automática
        after_hours_msg = BusinessHoursService.get_after_hours_message(tenant, department)
        
        if not after_hours_msg:
            # Sem mensagem configurada = não envia nada
            logger.info(f"Mensagem fora de horário recebida, mas sem mensagem automática configurada")
            return True, None
        
        # ✅ VERIFICAÇÃO: Se é grupo, verificar se reply_to_groups está habilitado
        is_group = conversation.conversation_type == 'group'
        if is_group and not after_hours_msg.reply_to_groups:
            logger.info(f"⏰ [BUSINESS HOURS] Mensagem recebida em grupo fora de horário, mas 'reply_to_groups' está desabilitado - não enviando mensagem automática")
            return True, None
        
        # Formata mensagem
        context = {
            'contact_name': conversation.contact_name or 'Cliente',
            'department_name': department.name if department else 'Atendimento',
            'next_open_time': next_open_time or 'Em breve',
            'message_time': message.created_at.astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y às %H:%M'),
            'message_content': (message.content or '')[:100],
            'contact_phone': conversation.contact_phone,
        }
        
        formatted_message = BusinessHoursService.format_message_template(
            after_hours_msg.message_template,
            context
        )
        
        # Cria mensagem automática
        auto_message = Message.objects.create(
            conversation=conversation,
            content=formatted_message,
            direction='outgoing',
            status='pending',
            is_internal=False,
            metadata={
                'is_after_hours_auto': True,
                'original_message_id': str(message.id),
                'next_open_time': next_open_time,
            }
        )
        
        logger.info(f"📨 [BUSINESS HOURS] Mensagem automática criada: {auto_message.id}")
        
        # ✅ CRÍTICO: Enfileira mensagem APENAS após commit da transação
        # Isso garante que a mensagem esteja no banco quando o worker tentar buscá-la
        def enqueue_message_after_commit():
            try:
                from apps.chat.tasks import send_message_to_evolution
                send_message_to_evolution.delay(str(auto_message.id))
                logger.info(f"✅ [BUSINESS HOURS] Mensagem automática enfileirada para envio: {auto_message.id}")
            except Exception as e:
                logger.error(f"❌ [BUSINESS HOURS] Erro ao enfileirar mensagem automática: {e}", exc_info=True)
                # Não re-raise - mensagem já foi criada, pode ser enviada manualmente depois
        
        transaction.on_commit(enqueue_message_after_commit)
        
        return True, auto_message
    
    @staticmethod
    @transaction.atomic
    def create_after_hours_task(
        conversation: Conversation,
        message: Message,
        tenant,
        department=None
    ) -> Optional[Task]:
        """
        Cria tarefa automática para retorno ao cliente quando mensagem é recebida fora de horário.
        
        Validações realizadas:
        - Verifica se configuração existe e está ativa
        - Verifica se criação de tarefa está habilitada
        - Verifica se mensagem está realmente fora de horário
        - Verifica se já existe tarefa para esta mensagem (evita duplicatas)
        - Cria ou busca contato relacionado
        
        Args:
            conversation: Conversa onde a mensagem foi recebida
            message: Mensagem recebida fora de horário
            tenant: Tenant da conversa
            department: Departamento da conversa (opcional)
        
        Returns:
            Optional[Task]: Tarefa criada ou None se não deve criar
        """
        logger.info(f"🔍 [BUSINESS HOURS TASK] ====== INICIANDO CRIAÇÃO DE TAREFA ======")
        logger.info(f"   Tenant: {tenant.name} (ID: {tenant.id})")
        logger.info(f"   Department: {department.name if department else 'None'}")
        logger.info(f"   Conversation: {conversation.id} | Phone: {conversation.contact_phone}")
        logger.info(f"   Message: {message.id} | Created: {message.created_at}")
        
        # ✅ VALIDAÇÃO 1: Busca configuração
        task_config = BusinessHoursService.get_after_hours_task_config(tenant, department)
        
        if not task_config:
            logger.warning(
                f"⚠️ [BUSINESS HOURS TASK] Configuração não encontrada - "
                f"tenant={tenant.name}, department={department.name if department else 'None'}"
            )
            return None
        
        logger.info(
            f"✅ [BUSINESS HOURS TASK] Configuração encontrada: "
            f"ID={task_config.id}, create_task_enabled={task_config.create_task_enabled}"
        )
        
        # ✅ VALIDAÇÃO 2: Verifica se criação está habilitada
        if not task_config.create_task_enabled:
            logger.info(
                f"⏭️ [BUSINESS HOURS TASK] Criação de tarefa está desabilitada na configuração "
                f"(create_task_enabled=False)"
            )
            return None
        
        # ✅ VALIDAÇÃO 3: Verifica se está realmente fora de horário
        is_open, next_open_time = BusinessHoursService.is_business_hours(
            tenant, department, message.created_at
        )
        
        logger.info(
            f"⏰ [BUSINESS HOURS TASK] Verificação de horário: "
            f"is_open={is_open}, next_open_time={next_open_time}"
        )
        
        if is_open:
            logger.warning(
                f"⚠️ [BUSINESS HOURS TASK] Mensagem está dentro do horário de atendimento - "
                f"não criando tarefa (mensagem criada em: {message.created_at})"
            )
            return None
        
        # ✅ VALIDAÇÃO 4: Verifica se já existe tarefa para esta mensagem (evita duplicatas)
        existing_task = Task.objects.filter(
            tenant=tenant,
            metadata__is_after_hours_auto=True,
            metadata__original_message_id=str(message.id),
            status__in=['pending', 'in_progress']
        ).first()
        
        if existing_task:
            logger.warning(
                f"⚠️ [BUSINESS HOURS TASK] Tarefa já existe para esta mensagem! "
                f"Task ID: {existing_task.id}, Title: {existing_task.title}"
            )
            logger.info(
                f"   ⏭️ Pulando criação de tarefa duplicada para mensagem {message.id}"
            )
            return existing_task
        
        # ✅ VALIDAÇÃO 5: Busca ou cria contato
        try:
            # ✅ CORREÇÃO: Normalizar telefone para garantir que não exceda 20 caracteres
            from apps.notifications.services import normalize_phone
            
            contact_phone_raw = conversation.contact_phone
            # Remover sufixos de grupo (@g.us) para buscar contato individual
            if '@g.us' in contact_phone_raw:
                # Para grupos, não criar contato (grupos não são contatos individuais)
                logger.warning(
                    f"⚠️ [BUSINESS HOURS TASK] Conversa é grupo ({contact_phone_raw}), "
                    f"não criando contato individual"
                )
                # Usar telefone do grupo truncado para relacionar tarefa
                contact_phone_normalized = contact_phone_raw[:20] if len(contact_phone_raw) > 20 else contact_phone_raw
            else:
                # Normalizar telefone individual
                contact_phone_normalized = normalize_phone(contact_phone_raw)
                if not contact_phone_normalized:
                    logger.warning(
                        f"⚠️ [BUSINESS HOURS TASK] Não foi possível normalizar telefone: {contact_phone_raw}"
                    )
                    contact_phone_normalized = contact_phone_raw[:20] if len(contact_phone_raw) > 20 else contact_phone_raw
            
            # ✅ CORREÇÃO CRÍTICA: Truncar telefone para máximo de 20 caracteres (limite do modelo)
            if len(contact_phone_normalized) > 20:
                logger.warning(
                    f"⚠️ [BUSINESS HOURS TASK] Telefone excede 20 caracteres ({len(contact_phone_normalized)}), "
                    f"truncando: {contact_phone_normalized[:20]}"
                )
                contact_phone_normalized = contact_phone_normalized[:20]
            
            # Buscar contato existente
            contact = Contact.objects.filter(
                tenant=tenant,
                phone=contact_phone_normalized
            ).first()
            
            if contact:
                logger.info(f"✅ [BUSINESS HOURS TASK] Contato encontrado: {contact.name} (ID: {contact.id})")
            else:
                # Cria contato básico se não existir (apenas para conversas individuais)
                if '@g.us' not in contact_phone_raw:
                    contact = Contact.objects.create(
                        tenant=tenant,
                        phone=contact_phone_normalized,
                        name=conversation.contact_name or 'Cliente',
                    )
                    logger.info(f"➕ [BUSINESS HOURS TASK] Contato criado: {contact.name} (ID: {contact.id})")
                else:
                    # Para grupos, não criar contato - usar None
                    contact = None
                    logger.info(f"ℹ️ [BUSINESS HOURS TASK] Conversa é grupo, não criando contato individual")
                    
        except Exception as e:
            logger.error(
                f"❌ [BUSINESS HOURS TASK] Erro ao buscar/criar contato: {e}",
                exc_info=True
            )
            contact = None  # Continuar sem contato se houver erro
        
        # ✅ FORMATAÇÃO: Prepara contexto para templates
        contact_name = conversation.contact_name or contact.name or 'Cliente'
        
        # ✅ CORREÇÃO: Converter horário para UTC-3 (America/Sao_Paulo) antes de formatar
        sao_paulo_tz = ZoneInfo('America/Sao_Paulo')
        message_time_local = message.created_at.astimezone(sao_paulo_tz)
        
        # ✅ NOVO: Informações de grupo e contato quando for grupo
        is_group = conversation.conversation_type == 'group'
        group_name = conversation.contact_name if is_group else None
        sender_name = message.sender_name if is_group else None
        sender_phone = message.sender_phone if is_group else None
        
        # Formatar informações do grupo e contato para exibição
        group_info = ''
        if is_group:
            group_info_parts = []
            if group_name:
                group_info_parts.append(f'Grupo: {group_name}')
            if sender_name:
                group_info_parts.append(f'Contato: {sender_name}')
            elif sender_phone:
                # Formatar telefone para exibição
                phone_display = sender_phone.replace('+', '').replace('@s.whatsapp.net', '')
                if len(phone_display) >= 10:
                    # Formatar como (XX) XXXXX-XXXX
                    phone_display = f"({phone_display[-11:-9]}) {phone_display[-9:-4]}-{phone_display[-4:]}"
                group_info_parts.append(f'Contato: {phone_display}')
            group_info = ' | '.join(group_info_parts) if group_info_parts else 'Grupo'
        
        context = {
            'contact_name': contact_name,
            'department_name': department.name if department else 'Atendimento',
            'message_time': message_time_local.strftime('%d/%m/%Y às %H:%M'),
            'message_content': (message.content or '')[:500] if task_config.include_message_preview else '',
            'next_open_time': next_open_time or 'Em breve',
            'contact_phone': conversation.contact_phone,
            'is_group': is_group,
            'group_name': group_name or '',
            'sender_name': sender_name or '',
            'sender_phone': sender_phone or '',
            'group_info': group_info,  # Formato: "Grupo: Nome do Grupo | Contato: Nome do Contato"
        }
        
        # Formata título e descrição usando templates
        try:
            task_title = BusinessHoursService.format_message_template(
                task_config.task_title_template,
                context
            )
            task_description = BusinessHoursService.format_message_template(
                task_config.task_description_template,
                context
            )
        except Exception as e:
            logger.error(
                f"❌ [BUSINESS HOURS TASK] Erro ao formatar templates: {e}",
                exc_info=True
            )
            return None
        
        # ✅ CÁLCULO: Data de vencimento (1h após início do próximo dia de atendimento)
        try:
            due_date = BusinessHoursService._calculate_task_due_date(
                tenant, department, message.created_at
            )
            logger.info(f"📅 [BUSINESS HOURS TASK] Vencimento calculado: {due_date}")
        except Exception as e:
            logger.error(
                f"❌ [BUSINESS HOURS TASK] Erro ao calcular vencimento: {e}",
                exc_info=True
            )
            # Fallback: vence em 24h
            from datetime import timedelta
            due_date = message.created_at + timedelta(hours=24)
            logger.warning(f"⚠️ [BUSINESS HOURS TASK] Usando vencimento fallback: {due_date}")
        
        # ✅ CRIAÇÃO: Tarefa automática
        # ✅ CORREÇÃO: department é obrigatório no modelo Task
        # Se auto_assign_to_department for False, usar department da conversa como fallback
        task_department = department if task_config.auto_assign_to_department else (department or conversation.department)
        
        # ✅ VALIDAÇÃO FINAL: Se não tiver department, usar department "Inbox"
        # ✅ CORREÇÃO: Inbox é criado automaticamente quando o tenant é criado
        # Apenas buscar o department "Inbox" existente (não criar)
        if not task_department:
            from apps.authn.models import Department
            # Buscar department "Inbox" existente (já criado automaticamente com o tenant)
            inbox_department = Department.objects.filter(
                tenant=tenant,
                name='Inbox'
            ).first()
            
            if inbox_department:
                task_department = inbox_department
                logger.info(
                    f"ℹ️ [BUSINESS HOURS TASK] Conversa {conversation.id} sem department atribuído. "
                    f"Tarefa será criada no department 'Inbox' (ID: {inbox_department.id})"
                )
            else:
                # Se Inbox não existe, é um erro do sistema (deveria ter sido criado com o tenant)
                logger.error(
                    f"❌ [BUSINESS HOURS TASK] Department 'Inbox' não encontrado para tenant {tenant.name}. "
                    f"O Inbox deveria ter sido criado automaticamente com o tenant."
                )
                # Fallback: buscar primeiro department do tenant
                task_department = Department.objects.filter(tenant=tenant).first()
                if task_department:
                    logger.warning(
                        f"⚠️ [BUSINESS HOURS TASK] Usando department '{task_department.name}' como fallback "
                        f"(conversa {conversation.id} sem department atribuído)"
                    )
                else:
                    logger.error(
                        f"❌ [BUSINESS HOURS TASK] Não é possível criar tarefa. "
                        f"Tenant {tenant.name} não tem departments cadastrados."
                    )
                    return None
        
        try:
            task = Task.objects.create(
                tenant=tenant,
                department=task_department,
                assigned_to=task_config.auto_assign_to_agent,
                title=task_title,
                description=task_description,
                priority=task_config.task_priority,
                due_date=due_date,
                status='pending',
                created_by=None,  # Sistema
                metadata={
                    'is_after_hours_auto': True,
                    'original_message_id': str(message.id),
                    'conversation_id': str(conversation.id),
                    'next_open_time': next_open_time,
                    'created_at': message.created_at.isoformat(),
                }
            )
            
            # Relaciona com contato (se existir)
            if contact:
                task.related_contacts.add(contact)
            else:
                logger.info(f"ℹ️ [BUSINESS HOURS TASK] Tarefa criada sem contato relacionado (grupo ou erro ao criar contato)")
            
            logger.info(f"✅ [BUSINESS HOURS TASK] ====== TAREFA CRIADA COM SUCESSO ======")
            logger.info(f"   Task ID: {task.id}")
            logger.info(f"   Title: {task.title}")
            logger.info(f"   Description: {task.description[:100]}...")
            logger.info(f"   Due Date: {task.due_date}")
            logger.info(f"   Priority: {task.priority}")
            logger.info(f"   Department: {task.department.name if task.department else 'None'}")
            logger.info(f"   Assigned To: {task.assigned_to.email if task.assigned_to else 'None'}")
            logger.info(f"   Contact: {contact.name} ({contact.phone})")
            
            return task
            
        except Exception as e:
            logger.error(
                f"❌ [BUSINESS HOURS TASK] Erro ao criar tarefa: {e}",
                exc_info=True
            )
            return None
    
    @staticmethod
    def _calculate_task_due_date(tenant, department=None, message_datetime: datetime = None) -> datetime:
        """
        Calcula a data de vencimento da tarefa.
        
        Regra: até 1h após o início do próximo dia de atendimento.
        
        Exemplo:
        - Mensagem: Sexta 22h
        - Próximo atendimento: Segunda 09:00
        - Vencimento: Segunda 10:00 (09:00 + 1h)
        """
        if message_datetime is None:
            message_datetime = django_timezone.now()
        
        # Busca horários de atendimento
        business_hours = BusinessHoursService.get_business_hours(tenant, department)
        
        if not business_hours:
            # Sem horário configurado = vence em 24h
            return message_datetime + timedelta(hours=24)
        
        # Converte para timezone configurado
        tz = ZoneInfo(business_hours.timezone)
        local_datetime = message_datetime.astimezone(tz)
        
        # Procura o próximo dia de atendimento (até 7 dias à frente)
        for days_ahead in range(1, 8):
            check_date = local_datetime.date() + timedelta(days=days_ahead)
            check_weekday = check_date.weekday()
            
            # Verifica se é feriado
            holidays = business_hours.holidays or []
            date_str = check_date.strftime('%Y-%m-%d')
            if date_str in holidays:
                continue
            
            # Mapeia weekday para campos
            day_configs = {
                0: ('monday_enabled', 'monday_start', 'Segunda-feira'),
                1: ('tuesday_enabled', 'tuesday_start', 'Terça-feira'),
                2: ('wednesday_enabled', 'wednesday_start', 'Quarta-feira'),
                3: ('thursday_enabled', 'thursday_start', 'Quinta-feira'),
                4: ('friday_enabled', 'friday_start', 'Sexta-feira'),
                5: ('saturday_enabled', 'saturday_start', 'Sábado'),
                6: ('sunday_enabled', 'sunday_start', 'Domingo'),
            }
            
            enabled_field, start_field, day_name = day_configs[check_weekday]
            is_enabled = getattr(business_hours, enabled_field)
            start_time = getattr(business_hours, start_field)
            
            if is_enabled:
                # Encontrou próximo dia de atendimento
                # Combina data + horário de início + 1 hora
                due_datetime_local = datetime.combine(check_date, start_time) + timedelta(hours=1)
                
                # ✅ CORREÇÃO: zoneinfo.ZoneInfo não tem método localize() (isso é do pytz)
                # Com zoneinfo, usamos replace() para adicionar timezone
                due_datetime_aware = due_datetime_local.replace(tzinfo=tz)
                due_datetime_utc = due_datetime_aware.astimezone(ZoneInfo('UTC'))
                
                logger.info(
                    f"Vencimento calculado: {day_name} {start_time} + 1h = {due_datetime_local.strftime('%d/%m/%Y %H:%M')} "
                    f"(UTC: {due_datetime_utc.strftime('%d/%m/%Y %H:%M')})"
                )
                
                # Retorna timezone-aware (Django espera isso)
                return due_datetime_utc
        
        # Se não encontrou nenhum dia de atendimento nos próximos 7 dias, vence em 7 dias
        fallback_date = local_datetime + timedelta(days=7)
        fallback_utc = fallback_date.astimezone(ZoneInfo('UTC'))
        logger.warning(f"Nenhum dia de atendimento encontrado nos próximos 7 dias, usando fallback: {fallback_utc}")
        return fallback_utc

