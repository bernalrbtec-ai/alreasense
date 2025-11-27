"""
Serviço para verificação de horários de atendimento e criação de tarefas automáticas.
"""
import logging
from datetime import datetime, time, timedelta
from typing import Optional, Tuple, Dict, Any
from zoneinfo import ZoneInfo
from django.utils import timezone as django_timezone
from django.db import transaction

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
            return True, None
        
        # Usa datetime fornecido ou agora
        if check_datetime is None:
            check_datetime = django_timezone.now()
        
        # Converte para timezone configurado
        tz = ZoneInfo(business_hours.timezone)
        local_datetime = check_datetime.astimezone(tz)
        local_date = local_datetime.date()
        local_time = local_datetime.time()
        weekday = local_datetime.weekday()  # 0=Monday, 6=Sunday
        
        # Verifica se é feriado
        holidays = business_hours.holidays or []
        date_str = local_date.strftime('%Y-%m-%d')
        if date_str in holidays:
            # É feriado = fechado
            next_open = BusinessHoursService._get_next_open_time(business_hours, local_datetime)
            return False, next_open
        
        # Mapeia weekday para campos do modelo
        day_configs = {
            0: ('monday_enabled', 'monday_start', 'monday_end'),    # Segunda
            1: ('tuesday_enabled', 'tuesday_start', 'tuesday_end'),  # Terça
            2: ('wednesday_enabled', 'wednesday_start', 'wednesday_end'),  # Quarta
            3: ('thursday_enabled', 'thursday_start', 'thursday_end'),  # Quinta
            4: ('friday_enabled', 'friday_start', 'friday_end'),    # Sexta
            5: ('saturday_enabled', 'saturday_start', 'saturday_end'),  # Sábado
            6: ('sunday_enabled', 'sunday_start', 'sunday_end'),   # Domingo
        }
        
        enabled_field, start_field, end_field = day_configs[weekday]
        is_enabled = getattr(business_hours, enabled_field)
        start_time = getattr(business_hours, start_field)
        end_time = getattr(business_hours, end_field)
        
        if not is_enabled:
            # Dia desabilitado = fechado
            next_open = BusinessHoursService._get_next_open_time(business_hours, local_datetime)
            return False, next_open
        
        # Verifica se está dentro do horário
        if start_time <= local_time <= end_time:
            return True, None
        
        # Fora do horário
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
        if department:
            config = AfterHoursTaskConfig.objects.filter(
                tenant=tenant,
                department=department,
                is_active=True
            ).first()
            if config:
                return config
        
        # Busca configuração geral do tenant
        config = AfterHoursTaskConfig.objects.filter(
            tenant=tenant,
            department__isnull=True,
            is_active=True
        ).first()
        
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
        
        # Formata mensagem
        context = {
            'contact_name': conversation.contact_name or 'Cliente',
            'department_name': department.name if department else 'Atendimento',
            'next_open_time': next_open_time or 'Em breve',
            'message_time': message.created_at.strftime('%d/%m/%Y às %H:%M'),
            'message_content': (message.content or '')[:100],
            'contact_phone': conversation.contact_phone,
        }
        
        formatted_message = BusinessHoursService.format_message_template(
            after_hours_msg.message_template,
            context
        )
        
        # Cria mensagem automática (não envia ainda - será enviada pelo sistema de envio)
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
        
        logger.info(f"Mensagem automática criada para fora de horário: {auto_message.id}")
        
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
        Cria tarefa automática para retorno ao cliente.
        
        Returns:
            Optional[Task]: Tarefa criada ou None
        """
        # Busca configuração
        task_config = BusinessHoursService.get_after_hours_task_config(tenant, department)
        
        if not task_config or not task_config.create_task_enabled:
            return None
        
        # Verifica se está fora de horário
        is_open, next_open_time = BusinessHoursService.is_business_hours(
            tenant, department, message.created_at
        )
        
        if is_open:
            # Dentro do horário = não cria tarefa
            return None
        
        # Busca ou cria contato
        contact = None
        try:
            contact = Contact.objects.get(
                tenant=tenant,
                phone=conversation.contact_phone
            )
        except Contact.DoesNotExist:
            # Cria contato básico se não existir
            contact = Contact.objects.create(
                tenant=tenant,
                phone=conversation.contact_phone,
                name=conversation.contact_name or 'Cliente',
            )
        
        # Formata título e descrição
        context = {
            'contact_name': conversation.contact_name or contact.name or 'Cliente',
            'department_name': department.name if department else 'Atendimento',
            'message_time': message.created_at.strftime('%d/%m/%Y às %H:%M'),
            'message_content': (message.content or '')[:500] if task_config.include_message_preview else '',
            'next_open_time': next_open_time or 'Em breve',
            'contact_phone': conversation.contact_phone,
        }
        
        task_title = BusinessHoursService.format_message_template(
            task_config.task_title_template,
            context
        )
        
        task_description = BusinessHoursService.format_message_template(
            task_config.task_description_template,
            context
        )
        
        # Calcula vencimento: até 1h após o início do próximo dia de atendimento
        due_date = BusinessHoursService._calculate_task_due_date(
            tenant, department, message.created_at
        )
        
        # Cria tarefa
        task = Task.objects.create(
            tenant=tenant,
            department=department if task_config.auto_assign_to_department else None,
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
            }
        )
        
        # Relaciona com contato
        task.related_contacts.add(contact)
        
        logger.info(f"Tarefa automática criada para fora de horário: {task.id}")
        
        return task
    
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
                
                # Converte para timezone aware e depois para UTC
                due_datetime_aware = tz.localize(due_datetime_local)
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

