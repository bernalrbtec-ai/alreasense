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
        
        ✅ CORREÇÃO: Buscar o mais recente (updated_at) mesmo se is_active não estiver definido.
        Isso garante que alterações recentes sejam refletidas.
        """
        if department:
            # Tenta buscar horário específico do departamento (mais recente primeiro)
            business_hours = BusinessHours.objects.filter(
                tenant=tenant,
                department=department
            ).order_by('-updated_at', '-created_at').first()
            
            if business_hours:
                logger.debug(f"⏰ [BUSINESS HOURS] Encontrado horário do departamento: {business_hours.id} (is_active={business_hours.is_active})")
                return business_hours
        
        # Busca horário geral do tenant (mais recente primeiro)
        business_hours = BusinessHours.objects.filter(
            tenant=tenant,
            department__isnull=True
        ).order_by('-updated_at', '-created_at').first()
        
        if business_hours:
            logger.debug(f"⏰ [BUSINESS HOURS] Encontrado horário geral: {business_hours.id} (is_active={business_hours.is_active})")
        
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
        
        # ✅ CORREÇÃO CRÍTICA: Se horário está desativado (is_active=False), considerar sempre aberto
        # Isso evita enviar mensagens automáticas quando o usuário desativou os horários
        if not business_hours.is_active:
            logger.info(f"⏰ [BUSINESS HOURS] Horário de atendimento DESATIVADO (is_active=False) para tenant={tenant.name}, department={department.name if department else 'Geral'} - considerando sempre aberto (não enviará mensagem automática)")
            return True, None
        
        logger.info(f"⏰ [BUSINESS HOURS] Verificando horário: tenant={tenant.name}, department={department.name if department else 'None'}, config_id={business_hours.id}, is_active={business_hours.is_active}")
        
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
    def _get_next_open_datetime(business_hours: BusinessHours, current_datetime: datetime) -> Optional[datetime]:
        """
        Calcula o próximo horário de abertura como datetime.
        
        Returns:
            Optional[datetime]: Próximo horário de abertura (timezone-aware) ou None se não encontrado
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
            
            if is_enabled and start_time:
                # Combina data + horário de início
                next_open_local = datetime.combine(check_date, start_time)
                # Adiciona timezone
                next_open_aware = next_open_local.replace(tzinfo=tz)
                # Converte para UTC (padrão Django)
                next_open_utc = next_open_aware.astimezone(ZoneInfo('UTC'))
                return next_open_utc
        
        return None
    
    @staticmethod
    def _get_next_open_time(business_hours: BusinessHours, current_datetime: datetime) -> str:
        """
        Calcula o próximo horário de abertura.
        
        Returns:
            str: Próximo horário formatado (ex: "Segunda-feira, 09:00")
        """
        next_open_dt = BusinessHoursService._get_next_open_datetime(business_hours, current_datetime)
        
        if next_open_dt:
            tz = ZoneInfo(business_hours.timezone)
            local_dt = next_open_dt.astimezone(tz)
            
            # Mapeia weekday para nome do dia
            day_names = {
                0: 'Segunda-feira',
                1: 'Terça-feira',
                2: 'Quarta-feira',
                3: 'Quinta-feira',
                4: 'Sexta-feira',
                5: 'Sábado',
                6: 'Domingo',
            }
            
            day_name = day_names[local_dt.weekday()]
            time_str = local_dt.strftime('%H:%M')
            return f"{day_name}, {time_str}"
        
        return "Em breve"
    
    @staticmethod
    def get_after_hours_message(tenant, department=None, sync_status=True) -> Optional[AfterHoursMessage]:
        """
        Busca mensagem automática para fora de horário.
        
        ✅ NOVO: Sincroniza is_active com BusinessHours antes de retornar.
        
        Args:
            tenant: Tenant para buscar mensagem
            department: Departamento (opcional)
            sync_status: Se True, sincroniza is_active com BusinessHours (padrão: True)
        
        Returns:
            AfterHoursMessage se encontrada, None caso contrário
            NOTA: Retorna a mensagem mesmo se is_active=False (para exibição no frontend)
        """
        # Buscar mensagem (sem filtrar por is_active primeiro)
        message = None
        if department:
            message = AfterHoursMessage.objects.filter(
                tenant=tenant,
                department=department
            ).first()
        
        if not message:
            # Busca mensagem geral do tenant
            message = AfterHoursMessage.objects.filter(
                tenant=tenant,
                department__isnull=True
            ).first()
        
        if message and sync_status:
            # ✅ NOVO: Sincronizar is_active com BusinessHours correspondente
            business_hours = BusinessHoursService.get_business_hours(tenant, department)
            if business_hours:
                if message.is_active != business_hours.is_active:
                    logger.debug(
                        f"🔄 [BUSINESS HOURS] Sincronizando mensagem automática: "
                        f"is_active={message.is_active} → {business_hours.is_active}"
                    )
                    message.is_active = business_hours.is_active
                    message.save(update_fields=['is_active'])
        
        return message
    
    @staticmethod
    def get_active_after_hours_message(tenant, department=None) -> Optional[AfterHoursMessage]:
        """
        Busca mensagem automática ATIVA para fora de horário.
        
        Usado pelo webhook para verificar se deve enviar mensagem automática.
        Retorna apenas se a mensagem estiver ativa.
        """
        message = BusinessHoursService.get_after_hours_message(tenant, department, sync_status=True)
        if message and message.is_active:
            return message
        return None
    
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
        
        # Fora de horário - busca mensagem automática ATIVA
        after_hours_msg = BusinessHoursService.get_active_after_hours_message(tenant, department)
        
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
        is_open, next_open_time_str = BusinessHoursService.is_business_hours(
            tenant, department, message.created_at
        )
        
        logger.info(
            f"⏰ [BUSINESS HOURS TASK] Verificação de horário: "
            f"is_open={is_open}, next_open_time={next_open_time_str}"
        )
        
        if is_open:
            logger.warning(
                f"⚠️ [BUSINESS HOURS TASK] Mensagem está dentro do horário de atendimento - "
                f"não criando tarefa (mensagem criada em: {message.created_at})"
            )
            return None
        
        # ✅ MELHORIA 1: Calcular datetime do próximo horário de abertura diretamente
        # Buscar business_hours para calcular datetime
        business_hours = BusinessHoursService.get_business_hours(tenant, department)
        if business_hours:
            next_open_dt = BusinessHoursService._get_next_open_datetime(business_hours, message.created_at)
            if next_open_dt is None:
                logger.warning(
                    f"⚠️ [BUSINESS HOURS TASK] Não foi possível calcular próximo horário de abertura. "
                    f"Usando fallback: agora + 24h"
                )
                next_open_dt = django_timezone.now() + timedelta(hours=24)
            else:
                logger.info(
                    f"✅ [BUSINESS HOURS TASK] Próximo horário de abertura calculado: {next_open_dt} "
                    f"(string formatada: {next_open_time_str})"
                )
        else:
            logger.warning(
                f"⚠️ [BUSINESS HOURS TASK] Business hours não encontrado. Usando fallback: agora + 24h"
            )
            next_open_dt = django_timezone.now() + timedelta(hours=24)
        
        # Garantir timezone aware (já deve estar, mas por segurança)
        if django_timezone.is_naive(next_open_dt):
            next_open_dt = django_timezone.make_aware(next_open_dt, ZoneInfo('UTC'))
        
        # ✅ MELHORIA 2: Validar se mensagem está dentro da janela de tempo
        if message.created_at > next_open_dt:
            logger.warning(
                f"⚠️ [BUSINESS HOURS TASK] Mensagem está FORA da janela de consolidação! "
                f"Message: {message.created_at}, Next Open: {next_open_dt}. Criando nova tarefa."
            )
            # Mensagem fora da janela, não consolidar
            existing_task_for_consolidation = None
        else:
            logger.info(f"🔍 [BUSINESS HOURS TASK] Buscando tarefa existente para consolidação...")
            logger.info(f"   Conversation ID: {conversation.id}")
            logger.info(f"   Contact Phone: {conversation.contact_phone}")
            logger.info(f"   Next Open Time: {next_open_dt}")
            logger.info(f"   Message Created At: {message.created_at}")
            logger.info(f"   Dentro da janela? {message.created_at <= next_open_dt}")
            
            # ✅ MELHORIA 3: Combinar queries (otimização de performance)
            # Buscar tarefa existente que pode ser:
            # 1. Tarefa para esta mensagem específica (evita duplicatas)
            # 2. Tarefa do mesmo contato/conversa dentro da janela (consolidação)
            existing_task_for_consolidation = Task.objects.filter(
                Q(
                    tenant=tenant,
                    metadata__is_after_hours_auto=True,
                    metadata__original_message_id=str(message.id),
                    status__in=['pending', 'in_progress']
                ) | Q(
                    tenant=tenant,
                    metadata__is_after_hours_auto=True,
                    metadata__conversation_id=str(conversation.id),
                    status__in=['pending', 'in_progress'],
                    created_at__lte=next_open_dt  # Criada antes do próximo horário de atendimento
                )
            ).order_by('-created_at').first()  # Pegar a mais recente
            
            # Verificar se é tarefa duplicada (mesma mensagem)
            if existing_task_for_consolidation:
                task_metadata_check = existing_task_for_consolidation.metadata or {}
                if task_metadata_check.get('original_message_id') == str(message.id):
                    logger.warning(
                        f"⚠️ [BUSINESS HOURS TASK] Tarefa já existe para esta mensagem! "
                        f"Task ID: {existing_task_for_consolidation.id}, Title: {existing_task_for_consolidation.title}"
                    )
                    logger.info(
                        f"   ⏭️ Pulando criação de tarefa duplicada para mensagem {message.id}"
                    )
                    return existing_task_for_consolidation
        
        if existing_task_for_consolidation:
            logger.info(f"✅ [BUSINESS HOURS TASK] Tarefa existente encontrada para consolidação!")
            logger.info(f"   Task ID: {existing_task_for_consolidation.id}")
            logger.info(f"   Created At: {existing_task_for_consolidation.created_at}")
            
            # Verificar quantidade de mensagens já consolidadas
            task_metadata = existing_task_for_consolidation.metadata or {}
            messages_list = task_metadata.get('messages', [])
            
            # ✅ MELHORIA 4: Otimizar busca de primeira mensagem (usar select_related se necessário)
            # Se não tem lista de mensagens, criar com a primeira mensagem
            if not messages_list:
                # Buscar primeira mensagem do metadata original
                first_message_id = task_metadata.get('original_message_id') or task_metadata.get('first_message_id')
                if first_message_id:
                    try:
                        first_message = Message.objects.only('id', 'created_at', 'content').get(id=first_message_id)
                        messages_list = [{
                            'message_id': str(first_message.id),
                            'created_at': first_message.created_at.isoformat(),
                            'content': (first_message.content or '')[:500]
                        }]
                    except Message.DoesNotExist:
                        logger.warning(f"⚠️ [BUSINESS HOURS TASK] Primeira mensagem não encontrada: {first_message_id}")
                        messages_list = []
            
            current_message_count = len(messages_list)
            logger.info(f"   Mensagens já consolidadas: {current_message_count}")
            
            # ✅ MELHORIA 5: Verificar duplicata ANTES de adicionar
            message_id_str = str(message.id)
            is_duplicate = any(m.get('message_id') == message_id_str for m in messages_list)
            
            if is_duplicate:
                logger.warning(
                    f"⚠️ [BUSINESS HOURS TASK] Mensagem {message.id} já está consolidada nesta tarefa! "
                    f"Task ID: {existing_task_for_consolidation.id}"
                )
                return existing_task_for_consolidation
            
            # Verificar limite de 20 mensagens
            MAX_MESSAGES_PER_TASK = 20
            if current_message_count >= MAX_MESSAGES_PER_TASK:
                logger.warning(
                    f"⚠️ [BUSINESS HOURS TASK] Tarefa já tem {current_message_count} mensagens "
                    f"(limite: {MAX_MESSAGES_PER_TASK}). Criando nova tarefa."
                )
                # Não consolidar, criar nova tarefa
                existing_task_for_consolidation = None
            else:
                # ✅ CONSOLIDAR: Adicionar nova mensagem à tarefa existente
                logger.info(f"📝 [BUSINESS HOURS TASK] Consolidando mensagem na tarefa existente...")
                
                # Adicionar nova mensagem à lista
                new_message_entry = {
                    'message_id': message_id_str,
                    'created_at': message.created_at.isoformat(),
                    'content': (message.content or '')[:500]  # Limitar tamanho
                }
                messages_list.append(new_message_entry)
                
                # Atualizar metadata
                updated_metadata = task_metadata.copy()
                updated_metadata['messages'] = messages_list
                updated_metadata['last_message_id'] = str(message.id)
                updated_metadata['last_message_at'] = message.created_at.isoformat()
                
                # Se não tinha first_message_id, adicionar agora
                if 'first_message_id' not in updated_metadata:
                    updated_metadata['first_message_id'] = messages_list[0]['message_id'] if messages_list else str(message.id)
                
                # ✅ MELHORIA 6: Cachear timezone conversion e otimizar formatação
                # Formatar descrição consolidada
                sao_paulo_tz = ZoneInfo('America/Sao_Paulo')  # Cachear fora do loop
                description_parts = [
                    f"Mensagens recebidas fora de horário ({len(messages_list)} mensagem{'s' if len(messages_list) > 1 else ''}):\n"
                ]
                
                # ✅ MELHORIA 7: Limitar tamanho da descrição (últimas 20 mensagens se muito longa)
                MAX_DESCRIPTION_MESSAGES = 20
                messages_to_show = messages_list[-MAX_DESCRIPTION_MESSAGES:] if len(messages_list) > MAX_DESCRIPTION_MESSAGES else messages_list
                
                if len(messages_list) > MAX_DESCRIPTION_MESSAGES:
                    description_parts.append(f"... ({len(messages_list) - MAX_DESCRIPTION_MESSAGES} mensagens anteriores ocultas)\n")
                
                for idx, msg_entry in enumerate(messages_to_show, 1):
                    try:
                        # ✅ MELHORIA: Exception específica e otimização de parse
                        msg_time_str = msg_entry['created_at'].replace('Z', '+00:00')
                        msg_time = datetime.fromisoformat(msg_time_str)
                        msg_time_local = msg_time.astimezone(sao_paulo_tz)
                        time_str = msg_time_local.strftime('%H:%M')
                    except (ValueError, KeyError, AttributeError) as e:
                        logger.debug(f"⚠️ [BUSINESS HOURS TASK] Erro ao formatar horário da mensagem: {e}")
                        time_str = '--:--'
                    
                    content_preview = msg_entry.get('content', '')[:200]  # Limitar preview
                    if len(msg_entry.get('content', '')) > 200:
                        content_preview += '...'
                    
                    description_parts.append(f"[{time_str}] {content_preview}")
                
                # Formatar next_open_time para exibição (usar string formatada ou datetime)
                if next_open_time_str:
                    next_open_display = next_open_time_str
                elif next_open_dt:
                    try:
                        next_open_local = next_open_dt.astimezone(sao_paulo_tz)
                        next_open_display = next_open_local.strftime('%d/%m/%Y às %H:%M')
                    except Exception as e:
                        logger.debug(f"⚠️ [BUSINESS HOURS TASK] Erro ao formatar next_open_dt: {e}")
                        next_open_display = 'Em breve'
                else:
                    next_open_display = 'Em breve'
                
                description_parts.append(f"\nPróximo horário de atendimento: {next_open_display}")
                
                updated_description = '\n'.join(description_parts)
                
                # ✅ MELHORIA 8: Limitar tamanho total da descrição (máximo 5000 caracteres)
                MAX_DESCRIPTION_LENGTH = 5000
                if len(updated_description) > MAX_DESCRIPTION_LENGTH:
                    updated_description = updated_description[:MAX_DESCRIPTION_LENGTH] + "\n... (descrição truncada)"
                    logger.warning(
                        f"⚠️ [BUSINESS HOURS TASK] Descrição truncada (tamanho: {len(updated_description)} caracteres)"
                    )
                
                # Atualizar tarefa
                existing_task_for_consolidation.metadata = updated_metadata
                existing_task_for_consolidation.description = updated_description
                # ✅ MANTER vencimento original (não recalcular)
                existing_task_for_consolidation.save(update_fields=['metadata', 'description'])
                
                logger.info(f"✅ [BUSINESS HOURS TASK] Mensagem consolidada com sucesso!")
                logger.info(f"   Total de mensagens na tarefa: {len(messages_list)}")
                logger.info(f"   Task ID: {existing_task_for_consolidation.id}")
                
                return existing_task_for_consolidation
        
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
            'next_open_time': next_open_time_str or 'Em breve',
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
            due_date = message.created_at + timedelta(hours=24)
            logger.warning(f"⚠️ [BUSINESS HOURS TASK] Usando vencimento fallback: {due_date}")
        
        # ✅ CRIAÇÃO: Tarefa automática
        # ✅ CORREÇÃO: department é obrigatório no modelo Task
        # Prioridade: task_department configurado > department da conversa > department do config > Inbox
        if task_config.task_department:
            # Se há um departamento específico configurado, usar ele
            task_department = task_config.task_department
            logger.info(f"✅ [BUSINESS HOURS TASK] Usando departamento configurado: {task_department.name} (ID: {task_department.id})")
        elif task_config.auto_assign_to_department:
            # Se auto_assign_to_department está True, usar department da conversa
            task_department = department or conversation.department
            if task_department:
                logger.info(f"✅ [BUSINESS HOURS TASK] Usando departamento da conversa: {task_department.name if task_department else 'None'} (ID: {task_department.id if task_department else 'None'})")
        else:
            # Se auto_assign_to_department está False, usar department do config ou conversa como fallback
            task_department = department or conversation.department
            if task_department:
                logger.info(f"✅ [BUSINESS HOURS TASK] Usando departamento da conversa/config: {task_department.name if task_department else 'None'}")
        
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
            # ✅ NOVO: Criar metadata com lista de mensagens (iniciando com a primeira)
            task_metadata = {
                'is_after_hours_auto': True,
                'original_message_id': str(message.id),
                'first_message_id': str(message.id),  # ✅ NOVO: ID da primeira mensagem
                'conversation_id': str(conversation.id),
                'next_open_time': next_open_time_str or (next_open_dt.isoformat() if next_open_dt else None),
                'next_open_datetime': next_open_dt.isoformat() if next_open_dt else None,  # ✅ NOVO: datetime para cálculos
                'created_at': message.created_at.isoformat(),
                'messages': [  # ✅ NOVO: Lista de mensagens consolidadas
                    {
                        'message_id': str(message.id),
                        'created_at': message.created_at.isoformat(),
                        'content': (message.content or '')[:500]  # Limitar tamanho
                    }
                ],
                'last_message_id': str(message.id),  # ✅ NOVO: ID da última mensagem
                'last_message_at': message.created_at.isoformat(),  # ✅ NOVO: Timestamp da última mensagem
            }
            
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
                metadata=task_metadata
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
        
        Regras:
        1. Se mensagem foi recebida ANTES do início do expediente do mesmo dia:
           → Vence no MESMO DIA, 1h após o início do expediente
        2. Se mensagem foi recebida DEPOIS do fim do expediente:
           → Vence no PRÓXIMO DIA de atendimento, 1h após o início do expediente
        
        Exemplos:
        - Mensagem: Segunda 7h (atendimento começa 9h)
          → Vencimento: Segunda 10h (9h + 1h)
        - Mensagem: Sexta 22h (atendimento termina 18h)
          → Vencimento: Segunda 10h (próximo dia 9h + 1h)
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
        current_date = local_datetime.date()
        current_time = local_datetime.time()
        current_weekday = current_date.weekday()
        
        # Mapeia weekday para campos
        day_configs = {
            0: ('monday_enabled', 'monday_start', 'monday_end', 'Segunda-feira'),
            1: ('tuesday_enabled', 'tuesday_start', 'tuesday_end', 'Terça-feira'),
            2: ('wednesday_enabled', 'wednesday_start', 'wednesday_end', 'Quarta-feira'),
            3: ('thursday_enabled', 'thursday_start', 'thursday_end', 'Quinta-feira'),
            4: ('friday_enabled', 'friday_start', 'friday_end', 'Sexta-feira'),
            5: ('saturday_enabled', 'saturday_start', 'saturday_end', 'Sábado'),
            6: ('sunday_enabled', 'sunday_start', 'sunday_end', 'Domingo'),
        }
        
        enabled_field, start_field, end_field, day_name = day_configs[current_weekday]
        is_enabled = getattr(business_hours, enabled_field)
        start_time = getattr(business_hours, start_field)
        end_time = getattr(business_hours, end_field)
        
        # ✅ NOVA LÓGICA: Verificar se mensagem foi recebida ANTES do início do expediente do mesmo dia
        if is_enabled and start_time and end_time:
            # Verifica se é feriado
            holidays = business_hours.holidays or []
            date_str = current_date.strftime('%Y-%m-%d')
            is_holiday = date_str in holidays
            
            if not is_holiday:
                # Se a mensagem foi recebida ANTES do início do expediente (ex: 7h, atendimento começa 9h)
                if current_time < start_time:
                    # ✅ CASO 1: Vence no mesmo dia, 1h após o início do expediente
                    due_datetime_local = datetime.combine(current_date, start_time) + timedelta(hours=1)
                    due_datetime_aware = due_datetime_local.replace(tzinfo=tz)
                    due_datetime_utc = due_datetime_aware.astimezone(ZoneInfo('UTC'))
                    
                    logger.info(
                        f"📅 [TASK DUE DATE] Mensagem recebida ANTES do expediente ({current_time.strftime('%H:%M')} < {start_time.strftime('%H:%M')})"
                    )
                    logger.info(
                        f"   Vencimento: {day_name} {start_time} + 1h = {due_datetime_local.strftime('%d/%m/%Y %H:%M')} "
                        f"(UTC: {due_datetime_utc.strftime('%d/%m/%Y %H:%M')})"
                    )
                    
                    return due_datetime_utc
                
                # Se a mensagem foi recebida DEPOIS do fim do expediente (ex: 22h, atendimento termina 18h)
                # ou durante o expediente mas fora de horário válido, buscar próximo dia
                if current_time >= end_time:
                    logger.info(
                        f"📅 [TASK DUE DATE] Mensagem recebida DEPOIS do expediente ({current_time.strftime('%H:%M')} >= {end_time.strftime('%H:%M')})"
                    )
                    logger.info(f"   Buscando próximo dia de atendimento...")
                else:
                    # Mensagem durante o expediente (não deveria criar tarefa, mas se criar, usar próximo dia)
                    logger.info(
                        f"📅 [TASK DUE DATE] Mensagem recebida DURANTE o expediente ({current_time.strftime('%H:%M')})"
                    )
                    logger.info(f"   Buscando próximo dia de atendimento...")
        
        # ✅ CASO 2: Buscar próximo dia de atendimento (até 7 dias à frente)
        for days_ahead in range(1, 8):
            check_date = current_date + timedelta(days=days_ahead)
            check_weekday = check_date.weekday()
            
            # Verifica se é feriado
            holidays = business_hours.holidays or []
            date_str = check_date.strftime('%Y-%m-%d')
            if date_str in holidays:
                continue
            
            enabled_field, start_field, end_field, day_name = day_configs[check_weekday]
            is_enabled = getattr(business_hours, enabled_field)
            start_time = getattr(business_hours, start_field)
            
            if is_enabled and start_time:
                # Encontrou próximo dia de atendimento
                # Combina data + horário de início + 1 hora
                due_datetime_local = datetime.combine(check_date, start_time) + timedelta(hours=1)
                
                # ✅ CORREÇÃO: zoneinfo.ZoneInfo não tem método localize() (isso é do pytz)
                # Com zoneinfo, usamos replace() para adicionar timezone
                due_datetime_aware = due_datetime_local.replace(tzinfo=tz)
                due_datetime_utc = due_datetime_aware.astimezone(ZoneInfo('UTC'))
                
                logger.info(
                    f"📅 [TASK DUE DATE] Vencimento calculado: {day_name} {start_time} + 1h = {due_datetime_local.strftime('%d/%m/%Y %H:%M')} "
                    f"(UTC: {due_datetime_utc.strftime('%d/%m/%Y %H:%M')})"
                )
                
                # Retorna timezone-aware (Django espera isso)
                return due_datetime_utc
        
        # Se não encontrou nenhum dia de atendimento nos próximos 7 dias, vence em 7 dias
        fallback_date = local_datetime + timedelta(days=7)
        fallback_utc = fallback_date.astimezone(ZoneInfo('UTC'))
        logger.warning(f"⚠️ [TASK DUE DATE] Nenhum dia de atendimento encontrado nos próximos 7 dias, usando fallback: {fallback_utc}")
        return fallback_utc

