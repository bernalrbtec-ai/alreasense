from django.apps import AppConfig
import logging
import threading
import time

logger = logging.getLogger(__name__)

# ✅ PROTEÇÃO: Flag global para evitar múltiplas inicializações
_scheduler_started = False
_recovery_started = False
_scheduler_lock = threading.Lock()


class CampaignsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.campaigns'
    verbose_name = 'Campanhas'
    
    def ready(self):
        """App pronto - Recuperar campanhas ativas"""
        global _scheduler_started, _recovery_started
        
        # ✅ PROTEÇÃO: Evitar múltiplas inicializações
        with _scheduler_lock:
            if _scheduler_started and _recovery_started:
                logger.info("ℹ️ [APPS] Scheduler já foi inicializado, ignorando chamada duplicada")
                return
            
        logger.info("✅ [APPS] App campanhas inicializado")
        
        # Recuperar campanhas ativas em thread separada para não bloquear startup
        def recover_active_campaigns():
            try:
                # Aguardar um pouco para garantir que o Django está totalmente carregado
                time.sleep(5)
                
                from .models import Campaign
                from .rabbitmq_consumer import get_rabbitmq_consumer
                
                # Buscar campanhas que realmente precisam ser processadas
                # Só recuperar campanhas que têm contatos pendentes E foram interrompidas por erro (não pelo usuário)
                from .models import CampaignContact
                
                campaigns_to_recover = []
                
                # Buscar campanhas que podem precisar de recuperação
                # 'running' = estava rodando quando o sistema parou (recuperar)
                # 'paused' = foi pausada pelo usuário (NÃO recuperar automaticamente, mas pode ter sido interrompida)
                active_campaigns = Campaign.objects.filter(status__in=['running', 'paused'])
                
                from django.utils import timezone
                from datetime import timedelta
                
                for campaign in active_campaigns:
                    # Verificar se tem contatos pendentes (incluindo 'sending' que pode estar travado)
                    pending_contacts = CampaignContact.objects.filter(
                        campaign=campaign, 
                        status__in=['pending', 'sending']
                    ).count()
                    
                    if campaign.status == 'running':
                        if pending_contacts > 0:
                            campaigns_to_recover.append(campaign)
                            logger.info(f"🔄 [RECOVERY] Campanha {campaign.id} - {campaign.name} (running) tem {pending_contacts} contatos pendentes - RECUPERANDO")
                        else:
                            logger.info(f"ℹ️ [RECOVERY] Campanha {campaign.id} - {campaign.name} (running) não tem contatos pendentes - marcando como concluída")
                            # Marcar como concluída se não tem contatos pendentes
                            campaign.status = 'completed'
                            campaign.completed_at = timezone.now()
                            campaign.save()
                    elif campaign.status == 'paused':
                        # ✅ CORREÇÃO: Campanhas pausadas também podem ter sido interrompidas por build
                        # Se foi atualizada recentemente (últimas 2 horas) e tem contatos pendentes,
                        # provavelmente foi interrompida por build, então recuperar
                        recent_threshold = timezone.now() - timedelta(hours=2)
                        was_recently_updated = campaign.updated_at and campaign.updated_at >= recent_threshold
                        
                        if pending_contacts > 0 and was_recently_updated:
                            # Provavelmente foi interrompida por build, recuperar
                            campaigns_to_recover.append(campaign)
                            logger.info(f"🔄 [RECOVERY] Campanha {campaign.id} - {campaign.name} (paused) atualizada recentemente com {pending_contacts} contatos pendentes - RECUPERANDO (possível interrupção por build)")
                        elif pending_contacts > 0:
                            logger.info(f"ℹ️ [RECOVERY] Campanha {campaign.id} - {campaign.name} (paused) tem {pending_contacts} contatos pendentes mas foi pausada há mais tempo - MANTENDO status pausado")
                        else:
                            logger.info(f"ℹ️ [RECOVERY] Campanha {campaign.id} - {campaign.name} (paused) não tem contatos pendentes - MANTENDO status")
                
                if campaigns_to_recover:
                    logger.info(f"🔄 [RECOVERY] Encontradas {len(campaigns_to_recover)} campanhas para recuperar")
                    
                    consumer = get_rabbitmq_consumer()
                    
                    for campaign in campaigns_to_recover:
                        try:
                            logger.info(f"🚀 [RECOVERY] Recuperando campanha {campaign.id} - {campaign.name}")
                            success = consumer.start_campaign(str(campaign.id))
                            
                            if success:
                                logger.info(f"✅ [RECOVERY] Campanha {campaign.id} recuperada com sucesso")
                            else:
                                logger.error(f"❌ [RECOVERY] Falha ao recuperar campanha {campaign.id}")
                                
                        except Exception as e:
                            logger.error(f"❌ [RECOVERY] Erro ao recuperar campanha {campaign.id}: {e}")
                else:
                    logger.info("ℹ️ [RECOVERY] Nenhuma campanha com contatos pendentes encontrada")
                
                logger.info("✅ [RECOVERY] Processo de recuperação de campanhas concluído")
                    
            except Exception as e:
                logger.error(f"❌ [RECOVERY] Erro no processo de recuperação: {e}")
        
        # ✅ NOVO: Função para verificar e iniciar campanhas agendadas automaticamente
        # ✅ ADICIONADO: Também verifica notificações de tarefas
        def check_scheduled_campaigns():
            """Verifica periodicamente campanhas agendadas e as inicia quando chega a hora
            Também verifica e envia notificações de tarefas"""
            try:
                # Aguardar um pouco para garantir que o Django está totalmente carregado
                time.sleep(10)
                
                from .models import Campaign
                from .rabbitmq_consumer import get_rabbitmq_consumer
                from django.utils import timezone
                from datetime import timedelta
                
                logger.info("=" * 60)
                logger.info("⏰ [SCHEDULER] Iniciando verificador de campanhas agendadas")
                logger.info("🔔 [SCHEDULER] Verificador de notificações de tarefas integrado")
                logger.info("=" * 60)
                
                while True:
                    try:
                        now = timezone.now()
                        
                        # ========== VERIFICAR CAMPANHAS AGENDADAS ==========
                        # Buscar campanhas agendadas que chegaram na hora
                        scheduled_campaigns = Campaign.objects.filter(
                            status='scheduled',
                            scheduled_at__isnull=False,
                            scheduled_at__lte=now
                        )
                        
                        if scheduled_campaigns.exists():
                            logger.info(f"⏰ [SCHEDULER] Encontradas {scheduled_campaigns.count()} campanha(s) agendada(s) para iniciar")
                            
                            consumer = get_rabbitmq_consumer()
                            
                            for campaign in scheduled_campaigns:
                                try:
                                    logger.info(f"🚀 [SCHEDULER] Iniciando campanha agendada: {campaign.id} - {campaign.name} (agendada para {campaign.scheduled_at})")
                                    
                                    # Iniciar campanha (muda status para 'running')
                                    campaign.start()
                                    
                                    # Log de início automático
                                    from .models import CampaignLog
                                    CampaignLog.log_campaign_started(campaign, None)  # None = iniciado automaticamente pelo scheduler
                                    
                                    # Iniciar processamento via RabbitMQ
                                    if consumer:
                                        success = consumer.start_campaign(str(campaign.id))
                                        if success:
                                            logger.info(f"✅ [SCHEDULER] Campanha {campaign.id} iniciada com sucesso")
                                        else:
                                            logger.error(f"❌ [SCHEDULER] Falha ao iniciar campanha {campaign.id} no RabbitMQ")
                                    else:
                                        logger.error(f"❌ [SCHEDULER] RabbitMQ Consumer não disponível para campanha {campaign.id}")
                                        
                                except Exception as e:
                                    logger.error(f"❌ [SCHEDULER] Erro ao iniciar campanha agendada {campaign.id}: {e}", exc_info=True)
                        
                        # ========== VERIFICAR NOTIFICAÇÕES DE TAREFAS ==========
                        try:
                            from apps.contacts.models import Task
                            from apps.authn.models import User
                            from apps.notifications.models import WhatsAppInstance
                            from apps.connections.models import EvolutionConnection
                            from channels.layers import get_channel_layer
                            from asgiref.sync import async_to_sync
                            import requests
                            import json
                            
                            minutes_before = 15  # Janela de notificação: 15 minutos antes
                            # ✅ MELHORIA: Ampliar janela para 10 minutos (de 10 a 20 minutos antes)
                            # Isso garante que não perca tarefas mesmo com delay na verificação
                            notification_window_start = now + timedelta(minutes=minutes_before - 5)
                            notification_window_end = now + timedelta(minutes=minutes_before + 5)
                            
                            # ✅ NOVO: Verificar também tarefas que chegaram no momento exato (últimos 5 minutos)
                            # Isso envia notificação quando o compromisso chega, não apenas 15 min antes
                            exact_time_window_start = now - timedelta(minutes=5)
                            exact_time_window_end = now + timedelta(minutes=1)
                            
                            # 1. Buscar tarefas para lembrete (15 minutos antes)
                            # ✅ CORREÇÃO: select_for_update não pode ser usado com select_related em campos nullable
                            # Solução: fazer select_for_update primeiro, depois select_related
                            from django.db import transaction
                            task_ids_reminder = []
                            with transaction.atomic():
                                # Primeiro: fazer select_for_update apenas na tabela Task (sem select_related)
                                tasks_reminder = Task.objects.select_for_update(skip_locked=True).filter(
                                due_date__gte=notification_window_start,
                                due_date__lte=notification_window_end,
                                    status__in=['pending', 'in_progress'],
                                notification_sent=False
                            ).exclude(
                                    status__in=['completed', 'cancelled']
                                ).values_list('id', flat=True)
                                
                                # Pegar IDs dentro da transação
                                task_ids_reminder = list(tasks_reminder)
                            
                            # Depois: buscar tarefas completas com select_related usando os IDs
                            tasks_reminder_list = []
                            if task_ids_reminder:
                                tasks_reminder_list = list(
                                    Task.objects.filter(id__in=task_ids_reminder)
                                    .select_related('assigned_to', 'created_by', 'tenant', 'department')
                                )
                            
                            # 2. ✅ NOVO: Buscar tarefas que chegaram no momento exato (últimos 5 minutos)
                            # Envia notificação "Compromisso chegou" mesmo se já foi notificado 15min antes
                            # ✅ CORREÇÃO: Filtrar por notification_sent=False para evitar duplicação
                            # ✅ CORREÇÃO: select_for_update não pode ser usado com select_related em campos nullable
                            task_ids_exact = []
                            with transaction.atomic():
                                # Primeiro: fazer select_for_update apenas na tabela Task (sem select_related)
                                tasks_exact_time = Task.objects.select_for_update(skip_locked=True).filter(
                                    due_date__gte=exact_time_window_start,
                                    due_date__lte=exact_time_window_end,
                                    status__in=['pending', 'in_progress'],
                                    notification_sent=False  # ✅ CORREÇÃO: Só notificar se não foi notificado antes
                                ).exclude(
                                    status__in=['completed', 'cancelled']
                                ).values_list('id', flat=True)
                                
                                # Pegar IDs dentro da transação
                                task_ids_exact = list(tasks_exact_time)
                            
                            # Depois: buscar tarefas completas com select_related usando os IDs
                            tasks_exact_time_list = []
                            if task_ids_exact:
                                tasks_exact_time_list = list(
                                    Task.objects.filter(id__in=task_ids_exact)
                                    .select_related('assigned_to', 'created_by', 'tenant', 'department')
                                )
                            
                            total_reminder = len(tasks_reminder_list)
                            total_exact = len(tasks_exact_time_list)
                            
                            # ✅ MELHORIA: Log sempre que houver tarefas OU a cada 1 minuto (para debug)
                            # Isso garante que vemos quando está verificando
                            should_log = total_reminder > 0 or total_exact > 0 or (int(time.time()) % 60 == 0)  # A cada 1 minuto
                            
                            if should_log:
                                logger.info(f'🔔 [TASK NOTIFICATIONS] Verificando lembretes (15min antes) entre {notification_window_start.strftime("%H:%M:%S")} e {notification_window_end.strftime("%H:%M:%S")}')
                                logger.info(f'🔔 [TASK NOTIFICATIONS] Verificando compromissos chegando (momento exato) entre {exact_time_window_start.strftime("%H:%M:%S")} e {exact_time_window_end.strftime("%H:%M:%S")}')
                                logger.info(f'🔔 [TASK NOTIFICATIONS] Hora atual: {now.strftime("%H:%M:%S")}')
                            
                            if total_reminder > 0 or total_exact > 0:
                                logger.info(f'📋 [TASK NOTIFICATIONS] Encontradas {total_reminder} tarefa(s) para lembrete (15min antes)')
                                logger.info(f'📋 [TASK NOTIFICATIONS] Encontradas {total_exact} tarefa(s) chegando agora (momento exato)')
                            
                            count_reminder = 0
                            count_exact = 0
                            
                            # Processar lembretes (15 minutos antes)
                            for task in tasks_reminder_list:
                                try:
                                    task.refresh_from_db()
                                    if task.status in ['completed', 'cancelled']:
                                        continue
                                    
                                    logger.info(f'📋 [TASK NOTIFICATIONS] Lembrete: {task.title} (ID: {task.id}) - {task.due_date.strftime("%d/%m/%Y %H:%M:%S")}')
                                    logger.info(f'   👤 Assigned to: {task.assigned_to.email if task.assigned_to else "Ninguém"}')
                                    logger.info(f'   👤 Created by: {task.created_by.email if task.created_by else "Ninguém"}')
                                    logger.info(f'   📞 Contatos relacionados: {task.related_contacts.count()}')
                                    
                                    notification_sent = False
                                    notifications_count = 0
                                    
                                    # Notificar usuário atribuído
                                    if task.assigned_to:
                                        logger.info(f'   📤 Notificando assigned_to: {task.assigned_to.email}')
                                        success = _notify_task_user(task, task.assigned_to, is_reminder=True)
                                        if success:
                                            notifications_count += 1
                                        notification_sent = notification_sent or success
                                    
                                    # Notificar criador (só se for diferente de assigned_to)
                                    if task.created_by and task.created_by != task.assigned_to:
                                        logger.info(f'   📤 Notificando created_by: {task.created_by.email}')
                                        success = _notify_task_user(task, task.created_by, is_reminder=True)
                                        if success:
                                            notifications_count += 1
                                        notification_sent = notification_sent or success
                                    elif task.created_by and task.created_by == task.assigned_to:
                                        logger.info(f'   ⏭️ Pulando created_by (mesmo usuário de assigned_to)')
                                    
                                    # ✅ NOVO: Notificar contatos relacionados (se habilitado)
                                    # Verificar se notificação de contatos está habilitada no metadata
                                    task_metadata = task.metadata or {}
                                    notify_contacts = task_metadata.get('notify_contacts', False)
                                    
                                    if notify_contacts and task.related_contacts.exists():
                                        contacts_notified = _notify_task_contacts(task, is_reminder=True)
                                        notification_sent = notification_sent or contacts_notified
                                    
                                    # ✅ MELHORIA: Só marcar como notificada se pelo menos uma notificação foi enviada com sucesso
                                    if notification_sent:
                                        # ✅ CORREÇÃO: Usar select_for_update para garantir atomicidade
                                        with transaction.atomic():
                                            task.refresh_from_db()
                                            if not task.notification_sent:  # Double-check
                                    task.notification_sent = True
                                    task.save(update_fields=['notification_sent'])
                                                count_reminder += 1
                                                logger.info(f'✅ [TASK NOTIFICATIONS] Lembrete enviado ({notifications_count} notificação(ões)) e marcado como notificado')
                                            else:
                                                logger.warning(f'⚠️ [TASK NOTIFICATIONS] Tarefa já estava marcada como notificada (race condition evitada)')
                                    else:
                                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] Nenhuma notificação foi enviada com sucesso, mantendo notification_sent=False para retry')
                                    
                                except Exception as e:
                                    logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao enviar lembrete para tarefa {task.id}: {e}', exc_info=True)
                            
                            # ✅ NOVO: Processar notificações no momento exato do compromisso
                            for task in tasks_exact_time_list:
                                try:
                                    task.refresh_from_db()
                                    if task.status in ['completed', 'cancelled']:
                                        continue
                                    
                                    # Verificar se já passou do horário (não notificar se passou mais de 1 minuto)
                                    if task.due_date < now - timedelta(minutes=1):
                                        continue
                                    
                                    logger.info(f'⏰ [TASK NOTIFICATIONS] Compromisso chegando: {task.title} (ID: {task.id}) - {task.due_date.strftime("%d/%m/%Y %H:%M:%S")}')
                                    
                                    notification_sent = False
                                    
                                    # Notificar usuário atribuído
                                    if task.assigned_to:
                                        success = _notify_task_user(task, task.assigned_to, is_reminder=False)
                                        notification_sent = notification_sent or success
                                    
                                    # Notificar criador
                                    if task.created_by and task.created_by != task.assigned_to:
                                        success = _notify_task_user(task, task.created_by, is_reminder=False)
                                        notification_sent = notification_sent or success
                                    
                                    # ✅ NOVO: Notificar contatos relacionados (se habilitado)
                                    # Verificar se notificação de contatos está habilitada no metadata
                                    task_metadata = task.metadata or {}
                                    notify_contacts = task_metadata.get('notify_contacts', False)
                                    
                                    if notify_contacts and task.related_contacts.exists():
                                        contacts_notified = _notify_task_contacts(task, is_reminder=False)
                                        notification_sent = notification_sent or contacts_notified
                                    
                                    if notification_sent:
                                        count_exact += 1
                                        logger.info(f'✅ [TASK NOTIFICATIONS] Notificação de compromisso enviada')
                                    
                                except Exception as e:
                                    logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao enviar notificação de compromisso para tarefa {task.id}: {e}', exc_info=True)
                            
                            if count_reminder > 0 or count_exact > 0:
                                logger.info(f'✅ [TASK NOTIFICATIONS] {count_reminder} lembrete(s) e {count_exact} notificação(ões) de compromisso enviadas')
                            else:
                                # ✅ MELHORIA: Log sempre que não há tarefas (para debug)
                                if should_log:
                                    logger.info(f'🔔 [TASK NOTIFICATIONS] Nenhuma tarefa para notificar no momento (verificando entre {notification_window_start.strftime("%H:%M:%S")} e {notification_window_end.strftime("%H:%M:%S")})')
                                    
                                    # ✅ DEBUG: Listar próximas tarefas para ajudar no diagnóstico
                                    from apps.contacts.models import Task
                                    upcoming_tasks = Task.objects.filter(
                                        due_date__gte=now,
                                        due_date__lte=now + timedelta(hours=24),
                                        status__in=['pending', 'in_progress']
                                    ).select_related('assigned_to', 'tenant').order_by('due_date')[:5]
                                    
                                    if upcoming_tasks.exists():
                                        logger.info(f'📅 [TASK NOTIFICATIONS] Próximas 5 tarefas nas próximas 24h:')
                                        for task in upcoming_tasks:
                                            logger.info(f'   - {task.title} (ID: {task.id}): {task.due_date.strftime("%d/%m/%Y %H:%M:%S")} | Notificada: {task.notification_sent} | Status: {task.status} | Tenant: {task.tenant.name if task.tenant else "N/A"}')
                                
                        except Exception as e:
                            logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao verificar tarefas: {e}', exc_info=True)
                        
                        # Aguardar 60 segundos antes da próxima verificação
                        time.sleep(60)
                        
                    except Exception as e:
                        logger.error(f"❌ [SCHEDULER] Erro no loop de verificação: {e}", exc_info=True)
                        # Aguardar antes de tentar novamente em caso de erro
                        time.sleep(60)
                        
            except Exception as e:
                logger.error(f"❌ [SCHEDULER] Erro fatal no verificador: {e}", exc_info=True)
        
        # ✅ Função auxiliar para notificar usuário sobre tarefa
        def _notify_task_user(task, user, is_reminder=True):
            """
            Notifica um usuário sobre uma tarefa.
            
            Args:
                task: Tarefa a ser notificada
                user: Usuário a ser notificado
                is_reminder: Se True, é lembrete (15min antes). Se False, é notificação no momento exato.
            
            Returns:
                bool: True se pelo menos uma notificação foi enviada com sucesso
            """
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from apps.notifications.models import WhatsAppInstance
            from apps.connections.models import EvolutionConnection
            import requests
            import json
            import re
            import time
            
            notification_sent = False
            
            # 1. Notificação no navegador (via WebSocket)
            try:
                channel_layer = get_channel_layer()
                if channel_layer:
                    due_time = task.due_date.strftime('%d/%m/%Y às %H:%M')
                    
                    # ✅ MELHORIA: Mensagem diferente para lembrete vs compromisso chegando
                    if is_reminder:
                    message = f"🔔 Lembrete: {task.title}\n📅 {due_time}"
                        notification_type = "lembrete"
                    else:
                        message = f"⏰ Compromisso chegando: {task.title}\n📅 {due_time}"
                        notification_type = "compromisso"
                    
                    async_to_sync(channel_layer.group_send)(
                        f"tenant_{task.tenant_id}",
                        {
                            'type': 'task_notification',
                            'task_id': str(task.id),
                            'title': task.title,
                            'message': message,
                            'due_date': task.due_date.isoformat(),
                            'user_id': str(user.id),
                            'notification_type': notification_type,
                        }
                    )
                    logger.info(f'✅ [TASK NOTIFICATIONS] Notificação no navegador ({notification_type}) enviada para {user.email}')
                    notification_sent = True
            except Exception as e:
                logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao enviar notificação no navegador: {e}', exc_info=True)
            
            # 2. Mensagem WhatsApp (se habilitado)
            logger.info(f'📱 [TASK NOTIFICATIONS] Verificando WhatsApp para {user.email}: notify_whatsapp={user.notify_whatsapp}, phone={user.phone if user.phone else "N/A"}')
            if user.notify_whatsapp and user.phone:
                try:
                    # Buscar instância WhatsApp ativa do tenant
                    instance = WhatsAppInstance.objects.filter(
                        tenant=task.tenant,
                        is_active=True,
                        status='active'
                    ).first()
                    
                    if not instance:
                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] Nenhuma instância WhatsApp ativa para tenant {task.tenant_id}')
                        return notification_sent  # Retornar status do WebSocket
                    
                    # ✅ MELHORIA: Usar api_url e api_key da instância diretamente
                    base_url = instance.api_url
                    api_key = instance.api_key
                    
                    if not base_url or not api_key:
                        # Fallback: buscar EvolutionConnection
                        connection = EvolutionConnection.objects.filter(
                            tenant=task.tenant,
                            is_active=True
                        ).first()
                        
                        if connection:
                            base_url = connection.base_url
                            api_key = connection.api_key
                        else:
                            logger.warning(f'⚠️ [TASK NOTIFICATIONS] Nenhuma conexão Evolution configurada para tenant {task.tenant_id}')
                            return notification_sent
                    
                    if not base_url or not api_key:
                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] API URL ou API Key não configurados')
                        return notification_sent
                    
                    # ✅ MELHORIA: Normalizar telefone do usuário (formato E.164) com validação
                    phone = user.phone.strip()
                    
                    # Remover todos os caracteres não numéricos exceto +
                    phone_clean = re.sub(r'[^\d+]', '', phone)
                    
                    # Validar formato básico
                    if not phone_clean or len(phone_clean) < 10:
                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] Telefone inválido para {user.email}: {phone}')
                        return notification_sent
                    
                    # Garantir formato E.164
                    if not phone_clean.startswith('+'):
                        if phone_clean.startswith('55'):
                            phone_clean = f'+{phone_clean}'
                        else:
                            # Remover zeros à esquerda e adicionar +55
                            phone_digits = ''.join(filter(str.isdigit, phone_clean))
                            if phone_digits.startswith('0'):
                                phone_digits = phone_digits[1:]
                            phone_clean = f'+55{phone_digits}'
                    
                    # Validar formato final (deve ter pelo menos +5511999999999 = 13 caracteres)
                    if len(phone_clean) < 13 or not phone_clean.startswith('+'):
                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] Telefone em formato inválido após normalização: {phone_clean}')
                        return notification_sent
                    
                    # ✅ MELHORIA: Formatar mensagem com mais contexto
                    due_time = task.due_date.strftime('%d/%m/%Y às %H:%M')
                    
                    if is_reminder:
                    message_text = f"🔔 *Lembrete de Tarefa*\n\n"
                    else:
                        message_text = f"⏰ *Compromisso Agendado*\n\n"
                    
                    message_text += f"*{task.title}*\n\n"
                    
                    # Adicionar descrição se houver
                    if task.description:
                        desc = task.description[:300].replace('\n', ' ')
                        message_text += f"{desc}\n\n"
                    
                    message_text += f"📅 *Data/Hora:* {due_time}\n"
                    
                    # Adicionar departamento
                    if task.department:
                        message_text += f"🏢 *Departamento:* {task.department.name}\n"
                    
                    # Adicionar prioridade
                    priority_display = dict(task.PRIORITY_CHOICES).get(task.priority, task.priority)
                    priority_emoji = {
                        'low': '🟢',
                        'medium': '🟡',
                        'high': '🟠',
                        'urgent': '🔴'
                    }.get(task.priority, '⚪')
                    message_text += f"{priority_emoji} *Prioridade:* {priority_display}\n"
                    
                    # Adicionar contatos relacionados se houver
                    if task.related_contacts.exists():
                        contacts = task.related_contacts.all()[:3]  # Máximo 3 contatos
                        contact_names = ', '.join([c.name for c in contacts])
                        if task.related_contacts.count() > 3:
                            contact_names += f" e mais {task.related_contacts.count() - 3}"
                        message_text += f"👤 *Contatos:* {contact_names}\n"
                    
                    # Adicionar descrição se houver
                    if task.description:
                        desc_notes = task.description[:200].replace('\n', ' ')
                        message_text += f"\n📝 *Descrição:* {desc_notes}"
                    
                    message_text += f"\n\nAcesse o sistema para mais detalhes."
                    
                    # ✅ MELHORIA: Usar instance_name da instância e base_url normalizado
                    base_url = base_url.rstrip('/')
                    url = f"{base_url}/message/sendText/{instance.instance_name}"
                    headers = {
                        'apikey': api_key,
                        'Content-Type': 'application/json'
                    }
                    payload = {
                        'number': phone_clean,
                        'text': message_text
                    }
                    
                    logger.info(f'📤 [TASK NOTIFICATIONS] Enviando WhatsApp para {phone_clean} (usuário: {user.email})')
                    logger.info(f'   URL: {url}')
                    logger.info(f'   Instância: {instance.instance_name}')
                    logger.info(f'   Tipo: {"Lembrete" if is_reminder else "Compromisso chegando"}')
                    
                    # ✅ MELHORIA: Retry em caso de falha
                    max_retries = 2
                    for attempt in range(max_retries):
                        try:
                    response = requests.post(url, json=payload, headers=headers, timeout=10)
                            
                    if response.status_code in [200, 201]:
                                logger.info(f'✅ [TASK NOTIFICATIONS] WhatsApp enviado com sucesso para {phone_clean}')
                                notification_sent = True
                                break
                    else:
                                logger.warning(f'⚠️ [TASK NOTIFICATIONS] Falha ao enviar WhatsApp (tentativa {attempt + 1}/{max_retries}): {response.status_code} - {response.text[:200]}')
                                if attempt < max_retries - 1:
                                    time.sleep(2)  # Aguardar 2 segundos antes de tentar novamente
                                
                        except requests.exceptions.RequestException as e:
                            logger.warning(f'⚠️ [TASK NOTIFICATIONS] Erro de conexão ao enviar WhatsApp (tentativa {attempt + 1}/{max_retries}): {e}')
                            if attempt < max_retries - 1:
                                time.sleep(2)
                    
                    if not notification_sent:
                        logger.error(f'❌ [TASK NOTIFICATIONS] Falha ao enviar WhatsApp após {max_retries} tentativas')
                        
                except Exception as e:
                    logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao enviar WhatsApp: {e}', exc_info=True)
        
            return notification_sent
        
        # ✅ NOVO: Função para notificar contatos relacionados
        def _notify_task_contacts(task, is_reminder=True):
            """
            Notifica contatos relacionados à tarefa via WhatsApp.
            
            Args:
                task: Tarefa a ser notificada
                is_reminder: Se True, é lembrete (15min antes). Se False, é notificação no momento exato.
            
            Returns:
                bool: True se pelo menos um contato foi notificado com sucesso
            """
            from apps.notifications.models import WhatsAppInstance
            from apps.connections.models import EvolutionConnection
            import requests
            import re
            
            if not task.related_contacts.exists():
                return False
            
            contacts_notified = False
            
            # Buscar instância WhatsApp ativa do tenant
            instance = WhatsAppInstance.objects.filter(
                tenant=task.tenant,
                is_active=True,
                status='active'
            ).first()
            
            if not instance:
                logger.warning(f'⚠️ [TASK NOTIFICATIONS] Nenhuma instância WhatsApp ativa para notificar contatos do tenant {task.tenant_id}')
                return False
            
            # Buscar servidor Evolution
            base_url = instance.api_url
            api_key = instance.api_key
            
            if not base_url or not api_key:
                connection = EvolutionConnection.objects.filter(
                    tenant=task.tenant,
                    is_active=True
                ).first()
                
                if connection:
                    base_url = connection.base_url
                    api_key = connection.api_key
                else:
                    logger.warning(f'⚠️ [TASK NOTIFICATIONS] Nenhuma conexão Evolution configurada para notificar contatos do tenant {task.tenant_id}')
                    return False
            
            if not base_url or not api_key:
                logger.warning(f'⚠️ [TASK NOTIFICATIONS] API URL ou API Key não configurados para notificar contatos')
                return False
            
            # Formatar mensagem para contatos
            due_time = task.due_date.strftime('%d/%m/%Y às %H:%M')
            
            if is_reminder:
                message_text = f"🔔 *Lembrete de Compromisso*\n\n"
            else:
                message_text = f"⏰ *Compromisso Agendado*\n\n"
            
            message_text += f"Olá! Temos um compromisso agendado:\n\n"
            message_text += f"*{task.title}*\n\n"
            
            if task.description:
                desc = task.description[:300].replace('\n', ' ')
                message_text += f"{desc}\n\n"
            
            message_text += f"📅 *Data/Hora:* {due_time}\n"
            
            if task.department:
                message_text += f"🏢 *Departamento:* {task.department.name}\n"
            
            priority_display = dict(task.PRIORITY_CHOICES).get(task.priority, task.priority)
            priority_emoji = {
                'low': '🟢',
                'medium': '🟡',
                'high': '🟠',
                'urgent': '🔴'
            }.get(task.priority, '⚪')
            message_text += f"{priority_emoji} *Prioridade:* {priority_display}\n"
            
            if task.assigned_to:
                assigned_name = f"{task.assigned_to.first_name} {task.assigned_to.last_name}".strip() or task.assigned_to.email
                message_text += f"👤 *Responsável:* {assigned_name}\n"
            
            message_text += f"\nAguardamos você!"
            
            # Notificar cada contato relacionado
            base_url = base_url.rstrip('/')
            url = f"{base_url}/message/sendText/{instance.instance_name}"
            headers = {
                'apikey': api_key,
                'Content-Type': 'application/json'
            }
            
            for contact in task.related_contacts.all():
                if not contact.phone:
                    logger.warning(f'⚠️ [TASK NOTIFICATIONS] Contato {contact.name} não tem telefone, pulando')
                    continue
                
                try:
                    # Normalizar telefone do contato
                    phone = contact.phone.strip()
                    phone_clean = re.sub(r'[^\d+]', '', phone)
                    
                    if not phone_clean or len(phone_clean) < 10:
                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] Telefone inválido para contato {contact.name}: {phone}')
                        continue
                    
                    # Garantir formato E.164
                    if not phone_clean.startswith('+'):
                        if phone_clean.startswith('55'):
                            phone_clean = f'+{phone_clean}'
                        else:
                            phone_digits = ''.join(filter(str.isdigit, phone_clean))
                            if phone_digits.startswith('0'):
                                phone_digits = phone_digits[1:]
                            phone_clean = f'+55{phone_digits}'
                    
                    # Validar formato final
                    if len(phone_clean) < 13 or not phone_clean.startswith('+'):
                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] Telefone em formato inválido para contato {contact.name}: {phone_clean}')
                        continue
                    
                    # Personalizar mensagem com nome do contato
                    personalized_message = message_text.replace('Olá!', f'Olá, {contact.name}!')
                    
                    payload = {
                        'number': phone_clean,
                        'text': personalized_message
                    }
                    
                    logger.info(f'📤 [TASK NOTIFICATIONS] Enviando WhatsApp para contato {contact.name} ({phone_clean})')
                    
                    # Retry em caso de falha
                    max_retries = 2
                    contact_notified = False
                    for attempt in range(max_retries):
                        try:
                            response = requests.post(url, json=payload, headers=headers, timeout=10)
                            
                            if response.status_code in [200, 201]:
                                logger.info(f'✅ [TASK NOTIFICATIONS] WhatsApp enviado para contato {contact.name} ({phone_clean})')
                                contact_notified = True
                                contacts_notified = True
                                break
                            else:
                                logger.warning(f'⚠️ [TASK NOTIFICATIONS] Falha ao enviar WhatsApp para contato {contact.name} (tentativa {attempt + 1}/{max_retries}): {response.status_code} - {response.text[:200]}')
                                if attempt < max_retries - 1:
                                    time.sleep(2)
                                
                        except requests.exceptions.RequestException as e:
                            logger.warning(f'⚠️ [TASK NOTIFICATIONS] Erro de conexão ao enviar WhatsApp para contato {contact.name} (tentativa {attempt + 1}/{max_retries}): {e}')
                            if attempt < max_retries - 1:
                                time.sleep(2)
                    
                    if not contact_notified:
                        logger.error(f'❌ [TASK NOTIFICATIONS] Falha ao enviar WhatsApp para contato {contact.name} após {max_retries} tentativas')
                        
                except Exception as e:
                    logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao notificar contato {contact.name}: {e}', exc_info=True)
            
            return contacts_notified
        
        # ✅ PROTEÇÃO: Iniciar threads apenas se ainda não foram iniciadas
        if not _recovery_started:
            recovery_thread = threading.Thread(target=recover_active_campaigns, daemon=True, name="CampaignRecovery")
        recovery_thread.start()
            _recovery_started = True
            logger.info("✅ [APPS] Thread de recuperação de campanhas iniciada")
        
        # ✅ NOVO: Iniciar thread de verificação de campanhas agendadas
        if not _scheduler_started:
            scheduler_thread = threading.Thread(target=check_scheduled_campaigns, daemon=True, name="CampaignScheduler")
        scheduler_thread.start()
            _scheduler_started = True
        logger.info("✅ [APPS] Verificador de campanhas agendadas iniciado")
