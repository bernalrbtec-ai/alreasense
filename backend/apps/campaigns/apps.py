from django.apps import AppConfig
from django.utils import timezone
from django.db.models import Q
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
        
        # ✅ PROTEÇÃO: Não iniciar threads durante scripts de migração/setup
        import sys
        import os
        
        # Verificar se estamos rodando um script de migração ou setup
        is_migration_script = any(
            'migrate' in arg or 
            'fix_' in arg or 
            'create_' in arg or
            'ensure_' in arg or
            'seed_' in arg or
            'check_' in arg
            for arg in sys.argv
        )
        
        # Verificar variável de ambiente para desabilitar scheduler
        disable_scheduler = os.environ.get('DISABLE_SCHEDULER', '0') == '1'
        
        if is_migration_script or disable_scheduler:
            logger.info("⏭️ [APPS] Scheduler desabilitado (script de migração/setup)")
            return
        
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
                # ✅ PERFORMANCE: Annotate pending_contacts para evitar N+1 queries
                from django.db.models import Count, Q
                active_campaigns = Campaign.objects.filter(
                    status__in=['running', 'paused']
                ).annotate(
                    pending_contacts_count=Count(
                        'campaign_contacts',
                        filter=Q(campaign_contacts__status__in=['pending', 'sending'])
                    )
                )
                
                from django.utils import timezone
                from datetime import timedelta
                
                for campaign in active_campaigns:
                    # ✅ PERFORMANCE: Usar valor annotado em vez de query separada
                    pending_contacts = campaign.pending_contacts_count
                    
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
                
                # Evitar poluir logs em produção: logar início apenas em DEBUG
                logger.debug("⏰ [SCHEDULER] Iniciando verificador de campanhas agendadas")
                logger.debug("🔔 [SCHEDULER] Verificador de notificações de tarefas integrado")
                
                while True:
                    try:
                        now = timezone.now()
                        
                        # Heartbeat do scheduler: manter apenas em DEBUG (muito ruído em produção)
                        current_second = int(time.time()) % 60
                        if current_second == 0 or current_second == 30:
                            logger.debug(
                                '🔄 [SCHEDULER] Ciclo de verificação - Hora: %s (UTC) / %s (Local)',
                                now.strftime("%H:%M:%S"),
                                timezone.localtime(now).strftime("%H:%M:%S"),
                            )
                        
                        # ========== VERIFICAR CAMPANHAS AGENDADAS ==========
                        # Buscar campanhas agendadas que chegaram na hora
                        # ✅ PERFORMANCE: Usar count() direto em vez de exists() + count()
                        scheduled_campaigns = Campaign.objects.filter(
                            status='scheduled',
                            scheduled_at__isnull=False,
                            scheduled_at__lte=now
                        )
                        scheduled_count = scheduled_campaigns.count()
                        
                        if scheduled_count > 0:
                            logger.info("⏰ [SCHEDULER] Encontradas %s campanha(s) agendada(s) para iniciar", scheduled_count)
                            
                            consumer = get_rabbitmq_consumer()
                            
                            for campaign in scheduled_campaigns:
                                try:
                                    logger.info(
                                        "🚀 [SCHEDULER] Iniciando campanha agendada: %s - %s (agendada para %s)",
                                        campaign.id, campaign.name, campaign.scheduled_at,
                                    )
                                    
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
                                # ✅ CORREÇÃO: Filtrar apenas agenda (não tarefas) para lembretes
                                tasks_reminder = Task.objects.select_for_update(skip_locked=True).filter(
                                due_date__gte=notification_window_start,
                                due_date__lte=notification_window_end,
                                    status__in=['pending', 'in_progress'],
                                notification_sent=False,
                                task_type='agenda'  # Apenas agenda para lembretes
                            ).exclude(
                                    status__in=['completed', 'cancelled']
                                ).values_list('id', flat=True)
                                
                                # Pegar IDs dentro da transação
                                task_ids_reminder = list(tasks_reminder)
                            
                            # Depois: buscar tarefas completas com select_related usando os IDs
                            # ✅ PERFORMANCE: Prefetch related_contacts para evitar N+1 queries
                            tasks_reminder_list = []
                            if task_ids_reminder:
                                tasks_reminder_list = list(
                                    Task.objects.filter(id__in=task_ids_reminder)
                                    .select_related('assigned_to', 'created_by', 'tenant', 'department')
                                    .prefetch_related('related_contacts')
                                )
                            
                            # 2. ✅ NOVO: Buscar tarefas que chegaram no momento exato (últimos 5 minutos)
                            # Envia notificação "Compromisso chegou" mesmo se já foi notificado 15min antes
                            # ✅ CORREÇÃO: Filtrar por notification_sent=False para evitar duplicação
                            # ✅ CORREÇÃO: select_for_update não pode ser usado com select_related em campos nullable
                            task_ids_exact = []
                            with transaction.atomic():
                                # Primeiro: fazer select_for_update apenas na tabela Task (sem select_related)
                                # ✅ CORREÇÃO: Filtrar apenas agenda (não tarefas) para lembretes
                                tasks_exact_time = Task.objects.select_for_update(skip_locked=True).filter(
                                    due_date__gte=exact_time_window_start,
                                    due_date__lte=exact_time_window_end,
                                    status__in=['pending', 'in_progress'],
                                    notification_sent=False,  # ✅ CORREÇÃO: Só notificar se não foi notificado antes
                                    task_type='agenda'  # Apenas agenda para lembretes
                                ).exclude(
                                    status__in=['completed', 'cancelled']
                                ).values_list('id', flat=True)
                                
                                # Pegar IDs dentro da transação
                                task_ids_exact = list(tasks_exact_time)
                            
                            # Depois: buscar tarefas completas com select_related usando os IDs
                            # ✅ CORREÇÃO: Excluir tarefas que já foram processadas no loop de lembrete
                            # para evitar duplicação quando as janelas se sobrepõem
                            # ✅ PERFORMANCE: Prefetch related_contacts para evitar N+1 queries
                            tasks_exact_time_list = []
                            if task_ids_exact:
                                # Excluir IDs que já foram processados no loop de lembrete
                                task_ids_exact_filtered = [tid for tid in task_ids_exact if tid not in task_ids_reminder]
                                if task_ids_exact_filtered:
                                    tasks_exact_time_list = list(
                                        Task.objects.filter(id__in=task_ids_exact_filtered)
                                        .select_related('assigned_to', 'created_by', 'tenant', 'department')
                                        .prefetch_related('related_contacts')
                                    )
                            
                            total_reminder = len(tasks_reminder_list)
                            total_exact = len(tasks_exact_time_list)
                            
                            # ✅ MELHORIA: Log sempre que houver tarefas OU a cada 30 segundos (para debug mais frequente)
                            # Isso garante que vemos quando está verificando
                            current_second = int(time.time()) % 60
                            should_log = total_reminder > 0 or total_exact > 0 or (current_second == 0 or current_second == 30)  # A cada 30 segundos
                            
                            if should_log:
                                logger.info(f'🔔 [TASK NOTIFICATIONS] Verificando lembretes (15min antes) entre {notification_window_start.strftime("%H:%M:%S")} e {notification_window_end.strftime("%H:%M:%S")}')
                                logger.info(f'🔔 [TASK NOTIFICATIONS] Verificando compromissos chegando (momento exato) entre {exact_time_window_start.strftime("%H:%M:%S")} e {exact_time_window_end.strftime("%H:%M:%S")}')
                                logger.info(f'🔔 [TASK NOTIFICATIONS] Hora atual: {now.strftime("%H:%M:%S")} (UTC) / {timezone.localtime(now).strftime("%H:%M:%S")} (Local)')
                                logger.info(f'🔔 [TASK NOTIFICATIONS] Total de tarefas encontradas: {total_reminder} lembrete(s) + {total_exact} exato(s)')
                            
                            if total_reminder > 0 or total_exact > 0:
                                logger.info(f'📋 [TASK NOTIFICATIONS] ⚠️ ATENÇÃO: Encontradas {total_reminder} tarefa(s) para lembrete (15min antes)')
                                logger.info(f'📋 [TASK NOTIFICATIONS] ⚠️ ATENÇÃO: Encontradas {total_exact} tarefa(s) chegando agora (momento exato)')
                            
                            count_reminder = 0
                            count_exact = 0
                            
                            # Processar lembretes (15 minutos antes)
                            for task in tasks_reminder_list:
                                try:
                                    # ✅ CRÍTICO: Adquirir lock ANTES de processar e marcar como notificada IMEDIATAMENTE
                                    # Isso garante que apenas uma instância processe, mesmo com múltiplas instâncias do scheduler
                                    # ✅ CORREÇÃO: select_for_update não pode ser usado com select_related em campos nullable
                                    # Solução: fazer select_for_update primeiro (sem select_related), depois buscar com select_related
                                    with transaction.atomic():
                                        # Primeiro: adquirir lock sem select_related (evita LEFT OUTER JOIN)
                                        locked_task_id = Task.objects.select_for_update(skip_locked=True).filter(
                                            id=task.id,
                                            notification_sent=False  # Só processar se ainda não foi notificada
                                        ).values_list('id', flat=True).first()
                                        
                                        if not locked_task_id:
                                            # Outra instância já está processando ou já foi notificada
                                            logger.info(f'⏭️ [TASK NOTIFICATIONS] Tarefa {task.id} está sendo processada por outra instância ou já foi notificada, pulando')
                                            continue
                                        
                                        # Segundo: buscar a tarefa com select_related (agora que já temos o lock)
                                        locked_task = Task.objects.select_related('assigned_to', 'created_by', 'tenant', 'department').get(id=locked_task_id)
                                        
                                        # Verificar status (pode ter mudado)
                                        if locked_task.status in ['completed', 'cancelled']:
                                            continue
                                        
                                        # ✅ CRÍTICO: Marcar como notificada IMEDIATAMENTE para evitar que outras instâncias processem
                                        # Isso garante que apenas esta instância processará, mesmo que as notificações falhem depois
                                        locked_task.notification_sent = True
                                        locked_task.save(update_fields=['notification_sent'])
                                        
                                        # Atualizar referência para usar a tarefa com lock
                                        task = locked_task
                                        
                                        logger.info(f'🔒 [TASK NOTIFICATIONS] Lock adquirido e notification_sent=True marcado para tarefa {task.id}')
                                    
                                    logger.info(f'📋 [TASK NOTIFICATIONS] Lembrete: {task.title} (ID: {task.id}) - {task.due_date.strftime("%d/%m/%Y %H:%M:%S")}')
                                    logger.info(f'   👤 Assigned to: {task.assigned_to.email if task.assigned_to else "Ninguém"}')
                                    logger.info(f'   👤 Created by: {task.created_by.email if task.created_by else "Ninguém"}')
                                    # ✅ PERFORMANCE: Usar len() em vez de count() após prefetch_related
                                    logger.info(f'   📞 Contatos relacionados: {len(task.related_contacts.all())}')
                                    logger.info(f'   🔍 notification_sent atual: {task.notification_sent}')
                                    
                                    notification_sent = False
                                    notifications_count = 0
                                    users_notified = set()  # ✅ NOVO: Rastrear usuários já notificados para evitar duplicação
                                    contacts_notified_set = set()  # ✅ NOVO: Rastrear contatos já notificados neste ciclo
                                    
                                    # Notificar usuário atribuído
                                    if task.assigned_to:
                                        logger.info(f'   📤 Notificando assigned_to: {task.assigned_to.email} (ID: {task.assigned_to.id})')
                                        success = _notify_task_user(task, task.assigned_to, is_reminder=True)
                                        if success:
                                            notifications_count += 1
                                            users_notified.add(task.assigned_to.id)
                                        notification_sent = notification_sent or success
                                    
                                    # Notificar criador (só se for diferente de assigned_to E ainda não foi notificado)
                                    if task.created_by and task.created_by.id not in users_notified:
                                        if task.created_by != task.assigned_to:
                                            logger.info(f'   📤 Notificando created_by: {task.created_by.email} (ID: {task.created_by.id})')
                                            success = _notify_task_user(task, task.created_by, is_reminder=True)
                                            if success:
                                                notifications_count += 1
                                                users_notified.add(task.created_by.id)
                                            notification_sent = notification_sent or success
                                        else:
                                            logger.info(f'   ⏭️ Pulando created_by (mesmo usuário de assigned_to)')
                                    elif task.created_by and task.created_by.id in users_notified:
                                        logger.info(f'   ⏭️ Pulando created_by (já notificado como assigned_to)')
                                    
                                    # ✅ NOVO: Notificar contatos relacionados (se habilitado)
                                    # Verificar se notificação de contatos está habilitada no metadata
                                    task_metadata = task.metadata or {}
                                    notify_contacts = task_metadata.get('notify_contacts', False)
                                    
                                    # ✅ PERFORMANCE: Usar len() em vez de exists() + count() após prefetch_related
                                    related_contacts_list = list(task.related_contacts.all())
                                    if notify_contacts and related_contacts_list:
                                        logger.info(f'   📞 Notificando {len(related_contacts_list)} contato(s) relacionado(s)')
                                        contacts_notified = _notify_task_contacts(task, is_reminder=True, contacts_notified_set=contacts_notified_set)
                                        notification_sent = notification_sent or contacts_notified
                                    
                                    # ✅ NOTA: notification_sent já foi marcado como True quando adquirimos o lock
                                    # Agora apenas contabilizar e logar o resultado
                                    if notification_sent:
                                        count_reminder += 1
                                        logger.info(f'✅ [TASK NOTIFICATIONS] Lembrete enviado ({notifications_count} notificação(ões))')
                                    else:
                                        # Se nenhuma notificação foi enviada, resetar notification_sent para permitir retry
                                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] Nenhuma notificação foi enviada com sucesso, resetando notification_sent=False para retry')
                                        with transaction.atomic():
                                            Task.objects.filter(id=task.id).update(notification_sent=False)
                                    
                                except Exception as e:
                                    logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao enviar lembrete para tarefa {task.id}: {e}', exc_info=True)
                            
                            # ✅ NOVO: Processar notificações no momento exato do compromisso
                            for task in tasks_exact_time_list:
                                try:
                                    # ✅ CRÍTICO: Adquirir lock ANTES de processar e marcar como notificada IMEDIATAMENTE
                                    # Isso garante que apenas uma instância processe, mesmo com múltiplas instâncias do scheduler
                                    # ✅ CORREÇÃO: select_for_update não pode ser usado com select_related em campos nullable
                                    # Solução: fazer select_for_update primeiro (sem select_related), depois buscar com select_related
                                    with transaction.atomic():
                                        # Primeiro: adquirir lock sem select_related (evita LEFT OUTER JOIN)
                                        locked_task_id = Task.objects.select_for_update(skip_locked=True).filter(
                                            id=task.id,
                                            notification_sent=False  # Só processar se ainda não foi notificada
                                        ).values_list('id', flat=True).first()
                                        
                                        if not locked_task_id:
                                            # Outra instância já está processando ou já foi notificada
                                            logger.info(f'⏭️ [TASK NOTIFICATIONS] Tarefa {task.id} está sendo processada por outra instância ou já foi notificada, pulando')
                                            continue
                                        
                                        # Segundo: buscar a tarefa com select_related (agora que já temos o lock)
                                        locked_task = Task.objects.select_related('assigned_to', 'created_by', 'tenant', 'department').get(id=locked_task_id)
                                        
                                        # Verificar status (pode ter mudado)
                                        if locked_task.status in ['completed', 'cancelled']:
                                            continue
                                        
                                        # Verificar se já passou do horário (não notificar se passou mais de 1 minuto)
                                        if locked_task.due_date < now - timedelta(minutes=1):
                                            continue
                                        
                                        # ✅ CRÍTICO: Marcar como notificada IMEDIATAMENTE para evitar que outras instâncias processem
                                        locked_task.notification_sent = True
                                        locked_task.save(update_fields=['notification_sent'])
                                        
                                        # Atualizar referência para usar a tarefa com lock
                                        task = locked_task
                                        
                                        logger.info(f'🔒 [TASK NOTIFICATIONS] Lock adquirido e notification_sent=True marcado para tarefa {task.id}')
                                    
                                    logger.info(f'⏰ [TASK NOTIFICATIONS] Compromisso chegando: {task.title} (ID: {task.id}) - {task.due_date.strftime("%d/%m/%Y %H:%M:%S")}')
                                    logger.info(f'   👤 Assigned to: {task.assigned_to.email if task.assigned_to else "Ninguém"}')
                                    logger.info(f'   👤 Created by: {task.created_by.email if task.created_by else "Ninguém"}')
                                    logger.info(f'   🔍 notification_sent atual: {task.notification_sent}')
                                    
                                    notification_sent = False
                                    notifications_count = 0
                                    users_notified = set()  # ✅ NOVO: Rastrear usuários já notificados para evitar duplicação
                                    contacts_notified_set = set()  # ✅ NOVO: Rastrear contatos já notificados neste ciclo
                                    
                                    # Notificar usuário atribuído
                                    if task.assigned_to:
                                        logger.info(f'   📤 Notificando assigned_to: {task.assigned_to.email} (ID: {task.assigned_to.id})')
                                        success = _notify_task_user(task, task.assigned_to, is_reminder=False)
                                        if success:
                                            notifications_count += 1
                                            users_notified.add(task.assigned_to.id)
                                        notification_sent = notification_sent or success
                                    
                                    # Notificar criador (só se for diferente de assigned_to E ainda não foi notificado)
                                    if task.created_by and task.created_by.id not in users_notified:
                                        if task.created_by != task.assigned_to:
                                            logger.info(f'   📤 Notificando created_by: {task.created_by.email} (ID: {task.created_by.id})')
                                            success = _notify_task_user(task, task.created_by, is_reminder=False)
                                            if success:
                                                notifications_count += 1
                                                users_notified.add(task.created_by.id)
                                            notification_sent = notification_sent or success
                                        else:
                                            logger.info(f'   ⏭️ Pulando created_by (mesmo usuário de assigned_to)')
                                    elif task.created_by and task.created_by.id in users_notified:
                                        logger.info(f'   ⏭️ Pulando created_by (já notificado como assigned_to)')
                                    
                                    # ✅ NOVO: Notificar contatos relacionados (se habilitado)
                                    # Verificar se notificação de contatos está habilitada no metadata
                                    task_metadata = task.metadata or {}
                                    notify_contacts = task_metadata.get('notify_contacts', False)
                                    
                                    # ✅ PERFORMANCE: Usar len() em vez de exists() + count() após prefetch_related
                                    related_contacts_list = list(task.related_contacts.all())
                                    if notify_contacts and related_contacts_list:
                                        logger.info(f'   📞 Notificando {len(related_contacts_list)} contato(s) relacionado(s)')
                                        contacts_notified = _notify_task_contacts(task, is_reminder=False, contacts_notified_set=contacts_notified_set)
                                        notification_sent = notification_sent or contacts_notified
                                    
                                    # ✅ NOTA: notification_sent já foi marcado como True quando adquirimos o lock
                                    # Agora apenas contabilizar e logar o resultado
                                    if notification_sent:
                                        count_exact += 1
                                        logger.info(f'✅ [TASK NOTIFICATIONS] Notificação de compromisso enviada ({notifications_count} notificação(ões))')
                                    else:
                                        # Se nenhuma notificação foi enviada, resetar notification_sent para permitir retry
                                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] Nenhuma notificação foi enviada com sucesso, resetando notification_sent=False para retry')
                                        with transaction.atomic():
                                            Task.objects.filter(id=task.id).update(notification_sent=False)
                                    
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
                                    # ✅ PERFORMANCE: Usar list() em vez de exists() para debug
                                    upcoming_tasks = list(
                                        Task.objects.filter(
                                            due_date__gte=now,
                                            due_date__lte=now + timedelta(hours=24),
                                            status__in=['pending', 'in_progress']
                                        ).select_related('assigned_to', 'tenant').order_by('due_date')[:5]
                                    )
                                    
                                    if upcoming_tasks:
                                        logger.info(f'📅 [TASK NOTIFICATIONS] Próximas 5 tarefas nas próximas 24h:')
                                        for task in upcoming_tasks:
                                            logger.info(f'   - {task.title} (ID: {task.id}): {task.due_date.strftime("%d/%m/%Y %H:%M:%S")} | Notificada: {task.notification_sent} | Status: {task.status} | Tenant: {task.tenant.name if task.tenant else "N/A"}')
                                
                        except Exception as e:
                            logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao verificar tarefas: {e}', exc_info=True)
                        
                        # ========== VERIFICAR NOTIFICAÇÕES DIÁRIAS PERSONALIZADAS ==========
                        try:
                            from apps.notifications.models import UserNotificationPreferences
                            from apps.notifications.services import send_whatsapp_notification, send_websocket_notification
                            
                            # Obter hora atual no timezone local (America/Sao_Paulo)
                            local_now = timezone.localtime(now)
                            current_time = local_now.time()
                            current_date = local_now.date()
                            
                            # Verificar notificações diárias (resumo diário)
                            check_user_daily_summaries(current_time, current_date)
                            
                            # Verificar notificações de departamento (resumo diário)
                            check_department_daily_summaries(current_time, current_date)
                            
                        except Exception as e:
                            logger.error(f'❌ [DAILY NOTIFICATIONS] Erro ao verificar notificações diárias: {e}', exc_info=True)
                        
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
                    # ✅ CORREÇÃO: Converter para timezone local antes de formatar
                    local_due_date = timezone.localtime(task.due_date)
                    due_time = local_due_date.strftime('%d/%m/%Y às %H:%M')
                    
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
                    logger.info(f'✅ [TASK NOTIFICATIONS] Notificação WebSocket ({notification_type}) enviada para {user.email} (ID: {user.id})')
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
                    
                    from apps.notifications.whatsapp_providers import get_sender
                    from apps.notifications.models import WhatsAppInstance, WhatsAppTemplate
                    from django.db.models import Q
                    sender = get_sender(instance)
                    if not sender:
                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] Provider não disponível para instância (tenant {task.tenant_id})')
                        return notification_sent
                    is_meta = getattr(instance, 'integration_type', None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD
                    wa_template = None
                    if is_meta:
                        wa_template = WhatsAppTemplate.objects.filter(
                            tenant=instance.tenant,
                            is_active=True,
                        ).filter(Q(wa_instance=instance) | Q(wa_instance__isnull=True)).order_by('name').first()
                        if not wa_template:
                            logger.warning(f'⚠️ [TASK NOTIFICATIONS] Instância Meta sem template ativo (tenant {task.tenant_id}); pulando envio')
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
                    # ✅ CORREÇÃO: Converter para timezone local antes de formatar
                    local_due_date = timezone.localtime(task.due_date)
                    due_time = local_due_date.strftime('%d/%m/%Y às %H:%M')
                    
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
                    # ✅ PERFORMANCE: Usar lista já carregada em vez de múltiplas queries
                    related_contacts_list = list(task.related_contacts.all())
                    if related_contacts_list:
                        contacts = related_contacts_list[:3]  # Máximo 3 contatos
                        contact_names = ', '.join([c.name for c in contacts])
                        if len(related_contacts_list) > 3:
                            contact_names += f" e mais {len(related_contacts_list) - 3}"
                        message_text += f"👤 *Contatos:* {contact_names}\n"
                    
                    # Adicionar descrição se houver
                    if task.description:
                        desc_notes = task.description[:200].replace('\n', ' ')
                        message_text += f"\n📝 *Descrição:* {desc_notes}"
                    
                    message_text += f"\n\nAcesse o sistema para mais detalhes."
                    
                    logger.info(f'📤 [TASK NOTIFICATIONS] Enviando WhatsApp para {phone_clean} (usuário: {user.email})')
                    logger.info(f'   Instância: {instance.instance_name}')
                    logger.info(f'   Tipo: {"Lembrete" if is_reminder else "Compromisso chegando"}')
                    
                    max_retries = 2
                    for attempt in range(max_retries):
                        try:
                            if is_meta and wa_template:
                                params = list(wa_template.body_parameters_default) if wa_template.body_parameters_default else [message_text]
                                ok, resp = sender.send_template(
                                    phone_clean,
                                    wa_template.template_id,
                                    wa_template.language_code or 'pt_BR',
                                    params,
                                )
                            else:
                                ok, resp = sender.send_text(phone_clean, message_text)
                            if ok:
                                logger.info(f'✅ [TASK NOTIFICATIONS] WhatsApp enviado com sucesso para {phone_clean} (usuário: {user.email}, ID: {user.id})')
                                notification_sent = True
                                break
                            logger.warning(f'⚠️ [TASK NOTIFICATIONS] Falha ao enviar WhatsApp (tentativa {attempt + 1}/{max_retries}): {resp.get("error", resp)}')
                            if attempt < max_retries - 1:
                                time.sleep(2)
                        except Exception as e:
                            logger.warning(f'⚠️ [TASK NOTIFICATIONS] Erro ao enviar WhatsApp (tentativa {attempt + 1}/{max_retries}): {e}')
                            if attempt < max_retries - 1:
                                time.sleep(2)
                    
                    if not notification_sent:
                        logger.error(f'❌ [TASK NOTIFICATIONS] Falha ao enviar WhatsApp após {max_retries} tentativas')
                        
                except Exception as e:
                    logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao enviar WhatsApp: {e}', exc_info=True)
        
            return notification_sent
        
        # ✅ NOVO: Função para notificar contatos relacionados
        def _notify_task_contacts(task, is_reminder=True, contacts_notified_set=None):
            """
            Notifica contatos relacionados à tarefa via WhatsApp.
            
            Args:
                task: Tarefa a ser notificada
                is_reminder: Se True, é lembrete (15min antes). Se False, é notificação no momento exato.
                contacts_notified_set: Set de IDs de contatos já notificados neste ciclo (para evitar duplicação)
            
            Returns:
                bool: True se pelo menos um contato foi notificado com sucesso
            """
            if contacts_notified_set is None:
                contacts_notified_set = set()
            from apps.notifications.models import WhatsAppInstance
            from apps.connections.models import EvolutionConnection
            import requests
            import re
            
            # ✅ PERFORMANCE: Verificar se há contatos usando prefetch_related
            related_contacts_list = list(task.related_contacts.all())
            if not related_contacts_list:
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
            
            from apps.notifications.whatsapp_providers import get_sender
            sender = get_sender(instance)
            if not sender:
                logger.warning(f'⚠️ [TASK NOTIFICATIONS] Provider não disponível para instância (tenant {task.tenant_id})')
                return False
            
            # Formatar mensagem para contatos
            # ✅ CORREÇÃO: Converter para timezone local antes de formatar
            from django.utils import timezone
            local_due_date = timezone.localtime(task.due_date)
            due_time = local_due_date.strftime('%d/%m/%Y às %H:%M')
            
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
            
            for contact in task.related_contacts.all():
                # ✅ CORREÇÃO: Verificar se contato já foi notificado neste ciclo
                if contact.id in contacts_notified_set:
                    logger.info(f'   ⏭️ [TASK NOTIFICATIONS] Contato {contact.name} (ID: {contact.id}) já foi notificado neste ciclo, pulando')
                    continue
                
                if not contact.phone:
                    logger.warning(f'⚠️ [TASK NOTIFICATIONS] Contato {contact.name} não tem telefone, pulando')
                    continue
                
                try:
                    logger.info(f'   📤 [TASK NOTIFICATIONS] Notificando contato: {contact.name} (ID: {contact.id}, Telefone: {contact.phone})')
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
                    
                    personalized_message = message_text.replace('Olá!', f'Olá, {contact.name}!')
                    logger.info(f'📤 [TASK NOTIFICATIONS] Enviando WhatsApp para contato {contact.name} ({phone_clean})')
                    max_retries = 2
                    contact_notified = False
                    for attempt in range(max_retries):
                        try:
                            ok, resp = sender.send_text(phone_clean, personalized_message)
                            if ok:
                                logger.info(f'✅ [TASK NOTIFICATIONS] WhatsApp enviado para contato {contact.name} ({phone_clean})')
                                contact_notified = True
                                contacts_notified = True
                                contacts_notified_set.add(contact.id)
                                break
                            logger.warning(f'⚠️ [TASK NOTIFICATIONS] Falha ao enviar WhatsApp para contato {contact.name} (tentativa {attempt + 1}/{max_retries}): {resp.get("error", resp)}')
                            if attempt < max_retries - 1:
                                time.sleep(2)
                        except Exception as e:
                            logger.warning(f'⚠️ [TASK NOTIFICATIONS] Erro ao enviar WhatsApp para contato {contact.name} (tentativa {attempt + 1}/{max_retries}): {e}')
                            if attempt < max_retries - 1:
                                time.sleep(2)
                    
                    if not contact_notified:
                        logger.error(f'❌ [TASK NOTIFICATIONS] Falha ao enviar WhatsApp para contato {contact.name} após {max_retries} tentativas')
                        
                except Exception as e:
                    logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao notificar contato {contact.name}: {e}', exc_info=True)
            
            return contacts_notified
        
        # ========== FUNÇÕES DE NOTIFICAÇÕES DIÁRIAS PERSONALIZADAS ==========
        
        def check_user_daily_summaries(current_time, current_date):
            """
            Verifica e envia resumos diários para usuários individuais.
            
            ⚠️ VALIDAÇÕES:
            - Verifica apenas usuários ativos
            - Verifica apenas tenants ativos
            - Considera timezone do tenant
            - Janela de ±1 minuto para evitar perda de notificações
            
            Args:
                current_time: time object no timezone local
                current_date: date object no timezone local
            """
            from apps.notifications.models import UserNotificationPreferences
            from apps.notifications.services import calculate_time_window, check_channels_enabled
            
            # ✅ OTIMIZAÇÃO: Usar função helper para calcular janela de tempo
            time_window_start, time_window_end = calculate_time_window(current_time, window_minutes=1)
            
            # ✅ CORREÇÃO: Usar select_for_update para evitar duplicação entre workers
            # Mesma lógica do lembrete de agenda
            from django.db import transaction
            
            preference_ids = []
            with transaction.atomic():
                # Primeiro: fazer select_for_update apenas na tabela de preferências (sem select_related)
                preferences_locked = UserNotificationPreferences.objects.select_for_update(skip_locked=True).filter(
                    daily_summary_enabled=True,
                    daily_summary_time__isnull=False,
                    daily_summary_time__gte=time_window_start,
                    daily_summary_time__lte=time_window_end,
                    tenant__status='active',
                    user__is_active=True
                ).values_list('id', flat=True)
                
                # Pegar IDs dentro da transação
                preference_ids = list(preferences_locked)
            
            # Depois: buscar preferências completas com select_related usando os IDs
            preferences = []
            if preference_ids:
                preferences = list(
                    UserNotificationPreferences.objects.filter(id__in=preference_ids)
                    .select_related('user', 'tenant', 'user__tenant')
                )
            
            count = 0
            for pref in preferences:
                try:
                    # ✅ CRÍTICO: Adquirir lock ANTES de processar e marcar como enviado IMEDIATAMENTE
                    # Isso garante que apenas uma instância processe, mesmo com múltiplas instâncias do scheduler
                    # Mesma lógica do lembrete de agenda
                    with transaction.atomic():
                        # Primeiro: adquirir lock sem select_related (evita LEFT OUTER JOIN)
                        # ✅ CORREÇÃO: Usar Q objects para permitir None OU data menor que hoje
                        # Isso corrige o problema onde NULL não passa na condição __lt
                        locked_pref_id = UserNotificationPreferences.objects.select_for_update(skip_locked=True).filter(
                            id=pref.id
                        ).filter(
                            Q(last_daily_summary_sent_date__isnull=True) | Q(last_daily_summary_sent_date__lt=current_date)
                        ).values_list('id', flat=True).first()
                        
                        if not locked_pref_id:
                            # Outra instância já está processando ou já foi enviado hoje
                            logger.info(f'⏭️ [DAILY NOTIFICATIONS] Preferência {pref.id} está sendo processada por outra instância ou já foi enviada hoje, pulando')
                            continue
                        
                        # Segundo: buscar a preferência com select_related (agora que já temos o lock)
                        locked_pref = UserNotificationPreferences.objects.select_related('user', 'tenant', 'user__tenant').get(id=locked_pref_id)
                        
                        # ✅ CRÍTICO: Marcar como enviado IMEDIATAMENTE para evitar que outras instâncias processem
                        # Isso garante que apenas esta instância processará, mesmo que as notificações falhem depois
                        locked_pref.last_daily_summary_sent_date = current_date
                        locked_pref.save(update_fields=['last_daily_summary_sent_date'])
                        
                        # Atualizar referência para usar a preferência com lock
                        pref = locked_pref
                        
                        logger.info(f'🔒 [DAILY NOTIFICATIONS] Lock adquirido e last_daily_summary_sent_date={current_date} marcado para preferência {pref.id}')
                    
                    # ✅ OTIMIZAÇÃO: Usar função helper para verificar canais
                    _, _, _, has_any = check_channels_enabled(pref, pref.user)
                    
                    if not has_any:
                        logger.debug(f'⏭️ [DAILY NOTIFICATIONS] Pulando {pref.user.email} - Nenhum canal habilitado')
                        continue
                    
                    # ✅ VALIDAÇÃO: Verificar se horário está configurado
                    if not pref.daily_summary_time:
                        logger.warning(f'⚠️ [DAILY NOTIFICATIONS] {pref.user.email} tem resumo habilitado mas sem horário configurado')
                        continue
                    
                    send_user_daily_summary(pref.user, pref, current_date)
                    count += 1
                except Exception as e:
                    logger.error(f'❌ [DAILY NOTIFICATIONS] Erro ao enviar resumo para {pref.user.email}: {e}', exc_info=True)
            
            if count > 0:
                logger.info(f'✅ [DAILY NOTIFICATIONS] {count} resumo(s) diário(s) enviado(s) para usuários')
        
        
        def send_user_daily_summary(user, preferences, current_date):
            """
            Envia resumo diário de tarefas para o usuário.
            
            ⚠️ VALIDAÇÕES:
            - Aplica filtros baseados nas preferências do usuário
            - Considera apenas tarefas do tenant do usuário
            - Filtra tarefas do dia atual (no timezone local)
            - Agrupa tarefas por status para facilitar leitura
            
            Args:
                user: Instância de User
                preferences: Instância de UserNotificationPreferences
                current_date: date object no timezone local
            """
            from apps.contacts.models import Task
            from apps.notifications.services import send_whatsapp_notification, send_websocket_notification
            
            # ✅ OTIMIZAÇÃO: Query otimizada com select_related e prefetch_related
            # ✅ CORREÇÃO: Filtrar apenas tarefas (não agenda) e que estão incluídas em notificações
            tasks = Task.objects.filter(
                assigned_to=user,
                tenant=user.tenant,
                task_type='task',  # Apenas tarefas, não agenda
                include_in_notifications=True  # Respeitar toggle de notificações
            ).exclude(
                status__in=['cancelled']  # Sempre excluir canceladas
            ).select_related('department', 'created_by', 'tenant', 'assigned_to').prefetch_related('related_contacts')
            
            # Aplicar filtros baseados nas preferências
            if not preferences.notify_pending:
                tasks = tasks.exclude(status='pending')
            if not preferences.notify_in_progress:
                tasks = tasks.exclude(status='in_progress')
            if not preferences.notify_completed:
                tasks = tasks.exclude(status='completed')
            
            # Filtrar tarefas do dia (hoje no timezone local)
            local_now = timezone.localtime(timezone.now())
            
            # ✅ CORREÇÃO: Incluir tanto tarefas agendadas (com due_date) quanto pendências (sem due_date)
            # Tarefas agendadas para hoje
            tasks_today = tasks.filter(
                due_date__date=current_date
            )
            
            # ✅ NOVO: Pendências sem data agendada (sempre incluir no resumo diário)
            pending_tasks_no_date = tasks.filter(
                due_date__isnull=True,
                status__in=['pending', 'in_progress']
            )
            
            # Tarefas atrasadas (independente da data)
            overdue_tasks = tasks.filter(
                due_date__lt=local_now,
                status__in=['pending', 'in_progress']
            )
            
            # ✅ NOVO: Agrupar pendências por departamento
            from collections import defaultdict
            pending_by_department = defaultdict(list)
            for task in pending_tasks_no_date:
                dept_name = task.department.name if task.department else 'Sem Departamento'
                pending_by_department[dept_name].append(task)
            
            # Agrupar por status (incluindo pendências sem data)
            tasks_by_status = {
                'pending': list(tasks_today.filter(status='pending')[:10]),  # Limitar para não sobrecarregar
                'in_progress': list(tasks_today.filter(status='in_progress')[:10]),
                'completed': list(tasks_today.filter(status='completed')[:10]),
                'overdue': list(overdue_tasks[:10]),
                'pending_no_date': dict(pending_by_department),  # ✅ NOVO: Pendências agrupadas por departamento
            }
            
            # ✅ VALIDAÇÃO: Verificar se há tarefas para notificar
            # Contar pendências sem data também
            pending_no_date_count = sum(len(tasks) for tasks in tasks_by_status.get('pending_no_date', {}).values())
            total_tasks = sum(len(tasks) for tasks in tasks_by_status.values() if isinstance(tasks, list)) + pending_no_date_count
            if total_tasks == 0:
                logger.debug(f'⏭️ [DAILY NOTIFICATIONS] Nenhuma tarefa para {user.email} hoje')
                return
            
            # Formatar mensagem
            message = format_daily_summary_message(user, tasks_by_status, current_date)
            
            # ✅ VALIDAÇÃO: Verificar se mensagem não está vazia
            if not message or len(message.strip()) == 0:
                logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Mensagem vazia para {user.email}, pulando envio')
                return
            
            # ✅ OTIMIZAÇÃO: Usar função helper para enviar notificações
            from apps.notifications.services import send_notifications
            
            notifications_sent, notifications_failed = send_notifications(
                user=user,
                preferences=preferences,
                message=message,
                notification_type='daily_summary',
                data={
                    'date': current_date.isoformat(),
                    'tasks': {
                        'pending': len(tasks_by_status['pending']),
                        'in_progress': len(tasks_by_status['in_progress']),
                        'completed': len(tasks_by_status['completed']),
                        'overdue': len(tasks_by_status['overdue']),
                    }
                },
                context_name=''
            )
            
            # ✅ CONTROLE: Logar resultado final
            if notifications_sent > 0:
                logger.info(f'✅ [DAILY NOTIFICATIONS] Resumo diário enviado para {user.email} ({notifications_sent} canal(is) enviado(s), {notifications_failed} falhou(aram))')
            else:
                logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Nenhuma notificação enviada para {user.email} (todos os {notifications_failed} canal(is) falharam)')
        
        
        def format_daily_summary_message(user, tasks_by_status, current_date):
            """
            Formata mensagem de resumo diário para WhatsApp.
            
            ⚠️ FORMATO:
            - Usa formatação Markdown do WhatsApp (*negrito*, _itálico_)
            - Limita quantidade de tarefas por seção (máx 5)
            - Inclui emojis para facilitar leitura
            - Formata data e hora no timezone local
            
            Args:
                user: Instância de User
                tasks_by_status: Dict com listas de tarefas agrupadas por status
                current_date: date object no timezone local
            
            Returns:
                str: Mensagem formatada para WhatsApp
            """
            # ✅ OTIMIZAÇÃO: Usar funções helper para formatação
            from apps.notifications.services import get_greeting, format_weekday_pt
            
            date_str = current_date.strftime('%d/%m/%Y')
            weekday_pt = format_weekday_pt(current_date)
            greeting = get_greeting()
            user_name = user.first_name or user.email.split('@')[0]
            
            # ✅ UX: Mensagem mais amigável e motivacional
            message = f"👋 *{greeting}, {user_name}!*\n\n"
            message += f"📋 *Resumo do seu dia - {weekday_pt}, {date_str}*\n\n"
            
            # Tarefas atrasadas (prioridade máxima)
            overdue = tasks_by_status['overdue']
            if overdue:
                message += f"⚠️ *Tarefas Atrasadas: {len(overdue)}*\n"
                for task in overdue[:5]:
                    local_due = timezone.localtime(task.due_date) if task.due_date else None
                    days_overdue = (timezone.now().date() - local_due.date()).days if local_due else 0
                    dept_name = task.department.name if task.department else ''
                    message += f"  • {task.title}"
                    if days_overdue > 0:
                        message += f" ({days_overdue} dia(s) atrasada)"
                    if dept_name:
                        message += f" [{dept_name}]"
                    message += "\n"
                if len(overdue) > 5:
                    message += f"  ... e mais {len(overdue) - 5} tarefa(s)\n"
                message += "\n"
            
            # Tarefas pendentes
            pending = tasks_by_status['pending']
            if pending:
                message += f"📝 *Tarefas para hoje: {len(pending)}*\n"
                for task in pending[:5]:
                    local_due = timezone.localtime(task.due_date) if task.due_date else None
                    due_time = local_due.strftime('%H:%M') if local_due else ''
                    dept_name = task.department.name if task.department else ''
                    message += f"  • {task.title}"
                    if due_time:
                        message += f" às {due_time}"
                    if dept_name:
                        message += f" [{dept_name}]"
                    message += "\n"
                if len(pending) > 5:
                    message += f"  ... e mais {len(pending) - 5} tarefa(s)\n"
                message += "\n"
            
            # Tarefas em progresso
            in_progress = tasks_by_status['in_progress']
            if in_progress:
                message += f"🔄 *Em andamento: {len(in_progress)}*\n"
                for task in in_progress[:5]:
                    dept_name = task.department.name if task.department else ''
                    message += f"  • {task.title}"
                    if dept_name:
                        message += f" [{dept_name}]"
                    message += "\n"
                if len(in_progress) > 5:
                    message += f"  ... e mais {len(in_progress) - 5} tarefa(s)\n"
                message += "\n"
            
            # Tarefas concluídas
            completed = tasks_by_status['completed']
            if completed:
                message += f"✅ *Concluídas hoje: {len(completed)}*\n"
                for task in completed[:5]:
                    dept_name = task.department.name if task.department else ''
                    message += f"  • {task.title}"
                    if dept_name:
                        message += f" [{dept_name}]"
                    message += "\n"
                if len(completed) > 5:
                    message += f"  ... e mais {len(completed) - 5} tarefa(s)\n"
                message += "\n"
            
            # ✅ NOVO: Pendências sem data agendada (agrupadas por departamento)
            pending_no_date = tasks_by_status.get('pending_no_date', {})
            if pending_no_date:
                total_pending_no_date = sum(len(tasks) for tasks in pending_no_date.values())
                message += f"📋 *Pendências (sem data agendada): {total_pending_no_date}*\n"
                # Agrupar por departamento
                for dept_name, dept_tasks in sorted(pending_no_date.items()):
                    message += f"\n  🏢 *{dept_name}: {len(dept_tasks)}*\n"
                    for task in dept_tasks[:5]:  # Máximo 5 por departamento
                        message += f"    • {task.title}"
                        if task.assigned_to:
                            assigned_name = f"{task.assigned_to.first_name} {task.assigned_to.last_name}".strip() or task.assigned_to.email
                            message += f" - {assigned_name}"
                        message += "\n"
                    if len(dept_tasks) > 5:
                        message += f"    ... e mais {len(dept_tasks) - 5} tarefa(s)\n"
                message += "\n"
            
            # ✅ UX: Mensagem motivacional baseada no progresso
            total_pending_no_date_count = sum(len(tasks) for tasks in pending_no_date.values())
            total = len(overdue) + len(pending) + len(in_progress) + len(completed) + total_pending_no_date_count
            completed_count = len(completed)
            
            if completed_count > 0 and total > 0:
                progress = (completed_count / total) * 100
                if progress >= 50:
                    message += f"🎉 *Ótimo trabalho! Você já concluiu {int(progress)}% das suas tarefas.*\n\n"
                elif progress >= 25:
                    message += f"💪 *Continue assim! Você já concluiu {int(progress)}% das suas tarefas.*\n\n"
            
            message += f"📊 *Total: {total} tarefa(s) no seu dia*\n\n"
            
            # ✅ UX: Call to action amigável
            if overdue:
                message += "💡 *Dica:* Priorize as tarefas atrasadas para manter tudo em dia!"
            elif pending:
                message += "✨ *Bom dia!* Você tem um dia produtivo pela frente!"
            elif completed_count == total and total > 0:
                message += "🌟 *Parabéns!* Você concluiu todas as suas tarefas de hoje!"
            
            return message
        
        
        def check_department_daily_summaries(current_time, current_date):
            """
            Verifica e envia resumos diários para gestores de departamento.
            
            ⚠️ VALIDAÇÕES:
            - Verifica apenas departamentos ativos
            - Verifica apenas tenants ativos
            - Considera timezone do tenant
            - Janela de ±1 minuto para evitar perda de notificações
            
            Args:
                current_time: time object no timezone local
                current_date: date object no timezone local
            """
            from apps.notifications.models import DepartmentNotificationPreferences
            from apps.notifications.services import calculate_time_window, check_channels_enabled
            from apps.authn.models import User  # ✅ CORREÇÃO: Importar User
            
            # ✅ OTIMIZAÇÃO: Usar função helper para calcular janela de tempo
            time_window_start, time_window_end = calculate_time_window(current_time, window_minutes=1)
            
            # ✅ CORREÇÃO: Usar select_for_update para evitar duplicação entre workers
            # Mesma lógica do lembrete de agenda e resumo de usuários
            from django.db import transaction
            
            preference_ids = []
            with transaction.atomic():
                # Primeiro: fazer select_for_update apenas na tabela de preferências (sem select_related)
                preferences_locked = DepartmentNotificationPreferences.objects.select_for_update(skip_locked=True).filter(
                    daily_summary_enabled=True,
                    daily_summary_time__isnull=False,
                    daily_summary_time__gte=time_window_start,
                    daily_summary_time__lte=time_window_end,
                    tenant__status='active'
                ).values_list('id', flat=True)
                
                # Pegar IDs dentro da transação
                preference_ids = list(preferences_locked)
            
            # Depois: buscar preferências completas com select_related usando os IDs
            preferences = []
            if preference_ids:
                preferences = list(
                    DepartmentNotificationPreferences.objects.filter(id__in=preference_ids)
                    .select_related('department', 'tenant', 'department__tenant')
                )
            
            count = 0
            for pref in preferences:
                try:
                    # ✅ CRÍTICO: Adquirir lock ANTES de processar e marcar como enviado IMEDIATAMENTE
                    # Isso garante que apenas uma instância processe, mesmo com múltiplas instâncias do scheduler
                    # Mesma lógica do lembrete de agenda e resumo de usuários
                    with transaction.atomic():
                        # Primeiro: adquirir lock sem select_related (evita LEFT OUTER JOIN)
                        # ✅ CORREÇÃO: Usar Q objects para permitir None OU data menor que hoje
                        # Isso corrige o problema onde NULL não passa na condição __lt
                        locked_pref_id = DepartmentNotificationPreferences.objects.select_for_update(skip_locked=True).filter(
                            id=pref.id
                        ).filter(
                            Q(last_daily_summary_sent_date__isnull=True) | Q(last_daily_summary_sent_date__lt=current_date)
                        ).values_list('id', flat=True).first()
                        
                        if not locked_pref_id:
                            # Outra instância já está processando ou já foi enviado hoje
                            logger.info(f'⏭️ [DAILY NOTIFICATIONS] Preferência de departamento {pref.id} está sendo processada por outra instância ou já foi enviada hoje, pulando')
                            continue
                        
                        # Segundo: buscar a preferência com select_related (agora que já temos o lock)
                        locked_pref = DepartmentNotificationPreferences.objects.select_related('department', 'tenant', 'department__tenant').get(id=locked_pref_id)
                        
                        # ✅ CRÍTICO: Marcar como enviado IMEDIATAMENTE para evitar que outras instâncias processem
                        # Isso garante que apenas esta instância processará, mesmo que as notificações falhem depois
                        locked_pref.last_daily_summary_sent_date = current_date
                        locked_pref.save(update_fields=['last_daily_summary_sent_date'])
                        
                        # Atualizar referência para usar a preferência com lock
                        pref = locked_pref
                        
                        logger.info(f'🔒 [DAILY NOTIFICATIONS] Lock adquirido e last_daily_summary_sent_date={current_date} marcado para preferência de departamento {pref.id}')
                    
                    # ✅ OTIMIZAÇÃO: Query otimizada com select_related para managers
                    managers = User.objects.filter(
                        departments=pref.department,
                        role__in=['gerente', 'admin'],
                        tenant=pref.tenant,
                        is_active=True
                    ).select_related('tenant').prefetch_related('departments')
                    
                    for manager in managers:
                        # ✅ OTIMIZAÇÃO: Usar função helper para verificar canais
                        _, _, _, has_any = check_channels_enabled(pref, manager)
                        
                        if not has_any:
                            logger.debug(f'⏭️ [DAILY NOTIFICATIONS] Pulando {manager.email} - Nenhum canal habilitado')
                            continue
                        
                        # ✅ VALIDAÇÃO: Verificar se horário está configurado
                        if not pref.daily_summary_time:
                            logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Departamento {pref.department.name} tem resumo habilitado mas sem horário configurado')
                            continue
                        
                        send_department_daily_summary(manager, pref.department, pref, current_date)
                        count += 1
                except Exception as e:
                    logger.error(f'❌ [DAILY NOTIFICATIONS] Erro ao enviar resumo de departamento {pref.department.name}: {e}', exc_info=True)
            
            if count > 0:
                logger.info(f'✅ [DAILY NOTIFICATIONS] {count} resumo(s) de departamento enviado(s)')
        
        
        def send_department_daily_summary(manager, department, preferences, current_date):
            """
            Envia resumo diário do departamento para o gestor.
            
            ⚠️ VALIDAÇÕES:
            - Aplica filtros baseados nas preferências do departamento
            - Considera apenas tarefas do tenant do departamento
            - Filtra tarefas do dia atual (no timezone local)
            - Limita quantidade de tarefas por notificação
            - Agrupa tarefas por status para facilitar leitura
            
            Args:
                manager: Instância de User (gestor)
                department: Instância de Department
                preferences: Instância de DepartmentNotificationPreferences
                current_date: date object no timezone local
            """
            from apps.authn.utils import get_department_tasks
            from apps.notifications.services import send_whatsapp_notification, send_websocket_notification
            from apps.contacts.models import Task  # ✅ CORREÇÃO: Importar Task
            
            # Buscar tarefas do departamento
            filters = {}
            if preferences.notify_only_critical:
                filters['priority'] = ['high', 'urgent']
            if preferences.notify_only_assigned:
                filters['assigned_only'] = True
            
            tasks = get_department_tasks(department, filters, tenant=department.tenant)
            
            # ✅ VALIDAÇÃO: Verificar se pelo menos um tipo de notificação está habilitado
            has_any_notification_type = (
                preferences.notify_pending or 
                preferences.notify_in_progress or 
                preferences.notify_completed or 
                preferences.notify_overdue
            )
            
            if not has_any_notification_type:
                logger.debug(f'⏭️ [DAILY NOTIFICATIONS] Departamento {department.name} tem todos os tipos de notificação desabilitados')
                return
            
            # Aplicar filtros baseados nas preferências
            if not preferences.notify_pending:
                tasks = tasks.exclude(status='pending')
            if not preferences.notify_in_progress:
                tasks = tasks.exclude(status='in_progress')
            if not preferences.notify_completed:
                tasks = tasks.exclude(status='completed')
            
            # Filtrar tarefas do dia (hoje no timezone local)
            local_now = timezone.localtime(timezone.now())
            
            # ✅ VALIDAÇÃO: Verificar se current_date é válido
            if current_date > local_now.date():
                logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Data futura recebida: {current_date}')
                return
            
            # ✅ CORREÇÃO: Incluir tanto tarefas agendadas (com due_date) quanto pendências (sem due_date)
            # Tarefas agendadas para hoje
            tasks_today = tasks.filter(due_date__date=current_date)
            
            # ✅ NOVO: Pendências sem data agendada (sempre incluir no resumo diário do departamento)
            pending_tasks_no_date = tasks.filter(
                due_date__isnull=True,
                status__in=['pending', 'in_progress']
            )
            
            # Tarefas atrasadas (independente da data, mas apenas se notify_overdue estiver habilitado)
            overdue_tasks = Task.objects.none()  # Inicializar como QuerySet vazio
            if preferences.notify_overdue:
                overdue_tasks = tasks.filter(
                    due_date__lt=local_now,
                    status__in=['pending', 'in_progress']
                )
            
            # ✅ Agrupar por status a partir do queryset ANTES de qualquer slice (Django não permite .filter() após slice)
            from collections import defaultdict
            pending_by_department = defaultdict(list)
            for task in pending_tasks_no_date:
                dept_name = task.department.name if task.department else 'Sem Departamento'
                pending_by_department[dept_name].append(task)
            
            tasks_by_status = {
                'pending': list(tasks_today.filter(status='pending')[:10]),
                'in_progress': list(tasks_today.filter(status='in_progress')[:10]),
                'completed': list(tasks_today.filter(status='completed')[:10]),
                'overdue': list(overdue_tasks[:10]),
                'pending_no_date': dict(pending_by_department),
            }
            
            # ✅ VALIDAÇÃO: Verificar se há tarefas para notificar
            # Contar pendências sem data também
            pending_no_date_count = sum(len(tasks) for tasks in tasks_by_status.get('pending_no_date', {}).values())
            total_tasks = sum(len(tasks) for tasks in tasks_by_status.values() if isinstance(tasks, list)) + pending_no_date_count
            if total_tasks == 0:
                logger.debug(f'⏭️ [DAILY NOTIFICATIONS] Nenhuma tarefa para departamento {department.name} hoje')
                return
            
            # Formatar mensagem
            message = format_department_daily_summary_message(manager, department, tasks_by_status, current_date)
            
            # ✅ VALIDAÇÃO: Verificar se mensagem não está vazia
            if not message or len(message.strip()) == 0:
                logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Mensagem vazia para departamento {department.name}, pulando envio')
                return
            
            # ✅ OTIMIZAÇÃO: Usar função helper para enviar notificações
            from apps.notifications.services import send_notifications
            
            notifications_sent, notifications_failed = send_notifications(
                user=manager,
                preferences=preferences,
                message=message,
                notification_type='department_daily_summary',
                data={
                    'department_id': str(department.id),
                    'department_name': department.name,
                    'date': current_date.isoformat(),
                    'tasks': {
                        'pending': len(tasks_by_status['pending']),
                        'in_progress': len(tasks_by_status['in_progress']),
                        'completed': len(tasks_by_status['completed']),
                        'overdue': len(tasks_by_status['overdue']),
                    }
                },
                context_name=f'(departamento: {department.name})'
            )
            
            # ✅ CONTROLE: Logar resultado final
            if notifications_sent > 0:
                logger.info(f'✅ [DAILY NOTIFICATIONS] Resumo de departamento enviado para {manager.email} ({notifications_sent} canal(is) enviado(s), {notifications_failed} falhou(aram))')
            else:
                logger.warning(f'⚠️ [DAILY NOTIFICATIONS] Nenhuma notificação enviada para {manager.email} (todos os {notifications_failed} canal(is) falharam)')
        
        
        def format_department_daily_summary_message(manager, department, tasks_by_status, current_date):
            """
            Formata mensagem de resumo diário do departamento para WhatsApp.
            
            ⚠️ FORMATO:
            - Usa formatação Markdown do WhatsApp (*negrito*, _itálico_)
            - Limita quantidade de tarefas por seção (máx 5)
            - Inclui emojis para facilitar leitura
            - Formata data e hora no timezone local
            
            Args:
                manager: Instância de User (gestor)
                department: Instância de Department
                tasks_by_status: Dict com listas de tarefas agrupadas por status
                current_date: date object no timezone local
            
            Returns:
                str: Mensagem formatada para WhatsApp
            """
            # ✅ OTIMIZAÇÃO: Usar funções helper para formatação
            from apps.notifications.services import get_greeting, format_weekday_pt
            
            date_str = current_date.strftime('%d/%m/%Y')
            weekday_pt = format_weekday_pt(current_date)
            greeting = get_greeting()
            manager_name = manager.first_name or manager.email.split('@')[0]
            
            # ✅ UX: Mensagem mais amigável e motivacional
            message = f"👋 *{greeting}, {manager_name}!*\n\n"
            message += f"🏢 *Resumo do Departamento {department.name}*\n"
            message += f"📋 *{weekday_pt}, {date_str}*\n\n"
            
            # Tarefas atrasadas (prioridade máxima)
            overdue = tasks_by_status['overdue']
            if overdue:
                message += f"⚠️ *Tarefas Atrasadas: {len(overdue)}*\n"
                for task in overdue[:5]:
                    local_due = timezone.localtime(task.due_date)
                    days_overdue = (timezone.now().date() - local_due.date()).days
                    message += f"  • {task.title}"
                    if days_overdue > 0:
                        message += f" ({days_overdue} dia(s) atrasada)"
                    if task.assigned_to:
                        assigned_name = f"{task.assigned_to.first_name} {task.assigned_to.last_name}".strip() or task.assigned_to.email
                        message += f" - {assigned_name}"
                    message += "\n"
                if len(overdue) > 5:
                    message += f"  ... e mais {len(overdue) - 5} tarefa(s)\n"
                message += "\n"
            
            # Tarefas pendentes
            pending = tasks_by_status['pending']
            if pending:
                message += f"📝 *Tarefas para hoje: {len(pending)}*\n"
                for task in pending[:5]:
                    local_due = timezone.localtime(task.due_date)
                    due_time = local_due.strftime('%H:%M')
                    message += f"  • {task.title} às {due_time}"
                    if task.assigned_to:
                        assigned_name = f"{task.assigned_to.first_name} {task.assigned_to.last_name}".strip() or task.assigned_to.email
                        message += f" - {assigned_name}"
                    message += "\n"
                if len(pending) > 5:
                    message += f"  ... e mais {len(pending) - 5} tarefa(s)\n"
                message += "\n"
            
            # Tarefas em progresso
            in_progress = tasks_by_status['in_progress']
            if in_progress:
                message += f"🔄 *Em andamento: {len(in_progress)}*\n"
                for task in in_progress[:5]:
                    message += f"  • {task.title}"
                    if task.assigned_to:
                        assigned_name = f"{task.assigned_to.first_name} {task.assigned_to.last_name}".strip() or task.assigned_to.email
                        message += f" - {assigned_name}"
                    message += "\n"
                if len(in_progress) > 5:
                    message += f"  ... e mais {len(in_progress) - 5} tarefa(s)\n"
                message += "\n"
            
            # Tarefas concluídas
            completed = tasks_by_status['completed']
            if completed:
                message += f"✅ *Concluídas hoje: {len(completed)}*\n"
                for task in completed[:5]:
                    message += f"  • {task.title}"
                    if task.assigned_to:
                        assigned_name = f"{task.assigned_to.first_name} {task.assigned_to.last_name}".strip() or task.assigned_to.email
                        message += f" - {assigned_name}"
                    message += "\n"
                if len(completed) > 5:
                    message += f"  ... e mais {len(completed) - 5} tarefa(s)\n"
                message += "\n"
            
            # ✅ NOVO: Pendências sem data agendada (agrupadas por departamento)
            pending_no_date = tasks_by_status.get('pending_no_date', {})
            if pending_no_date:
                total_pending_no_date = sum(len(tasks) for tasks in pending_no_date.values())
                message += f"📋 *Pendências (sem data agendada): {total_pending_no_date}*\n"
                # Agrupar por departamento
                for dept_name, dept_tasks in sorted(pending_no_date.items()):
                    message += f"\n  🏢 *{dept_name}: {len(dept_tasks)}*\n"
                    for task in dept_tasks[:5]:  # Máximo 5 por departamento
                        message += f"    • {task.title}"
                        if task.assigned_to:
                            assigned_name = f"{task.assigned_to.first_name} {task.assigned_to.last_name}".strip() or task.assigned_to.email
                            message += f" - {assigned_name}"
                        message += "\n"
                    if len(dept_tasks) > 5:
                        message += f"    ... e mais {len(dept_tasks) - 5} tarefa(s)\n"
                message += "\n"
            
            # ✅ UX: Mensagem motivacional baseada no progresso
            total_pending_no_date_count = sum(len(tasks) for tasks in pending_no_date.values())
            total = len(overdue) + len(pending) + len(in_progress) + len(completed) + total_pending_no_date_count
            completed_count = len(completed)
            
            if completed_count > 0 and total > 0:
                progress = (completed_count / total) * 100
                if progress >= 50:
                    message += f"🎉 *Ótimo trabalho! O departamento já concluiu {int(progress)}% das tarefas.*\n\n"
                elif progress >= 25:
                    message += f"💪 *Continue assim! O departamento já concluiu {int(progress)}% das tarefas.*\n\n"
            
            message += f"📊 *Total: {total} tarefa(s) no departamento hoje*\n\n"
            
            # ✅ UX: Call to action amigável
            if overdue:
                message += "💡 *Dica:* Priorize as tarefas atrasadas para manter tudo em dia!"
            elif pending:
                message += "✨ *Bom dia!* O departamento tem um dia produtivo pela frente!"
            elif completed_count == total and total > 0:
                message += "🌟 *Parabéns!* O departamento concluiu todas as tarefas de hoje!"
            
            return message
        
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
            logger.info("=" * 60)
            logger.info("✅ [APPS] Verificador de campanhas agendadas iniciado")
            logger.info("✅ [APPS] Verificador de notificações de tarefas iniciado")
            logger.info("=" * 60)
