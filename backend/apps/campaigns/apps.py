from django.apps import AppConfig
import logging
import threading
import time

logger = logging.getLogger(__name__)


class CampaignsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.campaigns'
    verbose_name = 'Campanhas'
    
    def ready(self):
        """App pronto - Recuperar campanhas ativas"""
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
                
                logger.info("⏰ [SCHEDULER] Iniciando verificador de campanhas agendadas")
                logger.info("🔔 [SCHEDULER] Verificador de notificações de tarefas integrado")
                
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
                            notification_window_start = now + timedelta(minutes=minutes_before - 1)
                            notification_window_end = now + timedelta(minutes=minutes_before + 1)
                            
                            # Buscar tarefas que estão no período de notificação
                            # ✅ IMPORTANTE: Excluir tarefas concluídas ou canceladas
                            tasks_to_notify = Task.objects.filter(
                                due_date__gte=notification_window_start,
                                due_date__lte=notification_window_end,
                                status__in=['pending', 'in_progress'],  # Apenas pendentes ou em andamento
                                notification_sent=False
                            ).exclude(
                                status__in=['completed', 'cancelled']  # ✅ Garantir que concluídas/canceladas não sejam notificadas
                            ).select_related('assigned_to', 'created_by', 'tenant', 'department')
                            
                            total_tasks = tasks_to_notify.count()
                            if total_tasks > 0:
                                logger.info(f'🔔 [TASK NOTIFICATIONS] Verificando tarefas entre {notification_window_start} e {notification_window_end}')
                                logger.info(f'📋 [TASK NOTIFICATIONS] Encontradas {total_tasks} tarefa(s) para notificar')
                            
                            count = 0
                            for task in tasks_to_notify:
                                try:
                                    # ✅ VERIFICAÇÃO ADICIONAL: Garantir que tarefa não foi concluída/cancelada
                                    # (pode ter sido alterada entre a query e agora)
                                    if task.status in ['completed', 'cancelled']:
                                        logger.info(f'⏭️ [TASK NOTIFICATIONS] Pulando tarefa {task.id} - status: {task.status}')
                                        continue
                                    
                                    # Notificar usuário atribuído (se houver)
                                    if task.assigned_to:
                                        _notify_task_user(task, task.assigned_to)
                                    
                                    # Notificar criador (se diferente do atribuído)
                                    if task.created_by and task.created_by != task.assigned_to:
                                        _notify_task_user(task, task.created_by)
                                    
                                    # Marcar como notificada
                                    task.notification_sent = True
                                    task.save(update_fields=['notification_sent'])
                                    count += 1
                                    
                                except Exception as e:
                                    logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao notificar tarefa {task.id}: {e}', exc_info=True)
                            
                            if count > 0:
                                logger.info(f'✅ [TASK NOTIFICATIONS] {count} tarefa(s) notificada(s)')
                                
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
        def _notify_task_user(task, user):
            """Notifica um usuário sobre uma tarefa"""
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from apps.notifications.models import WhatsAppInstance
            from apps.connections.models import EvolutionConnection
            import requests
            import json
            
            # 1. Notificação no navegador (via WebSocket)
            try:
                channel_layer = get_channel_layer()
                if channel_layer:
                    due_time = task.due_date.strftime('%d/%m/%Y às %H:%M')
                    message = f"🔔 Lembrete: {task.title}\n📅 {due_time}"
                    
                    async_to_sync(channel_layer.group_send)(
                        f"tenant_{task.tenant_id}",
                        {
                            'type': 'task_notification',
                            'task_id': str(task.id),
                            'title': task.title,
                            'message': message,
                            'due_date': task.due_date.isoformat(),
                            'user_id': str(user.id),
                        }
                    )
                    logger.info(f'✅ [TASK NOTIFICATIONS] Notificação no navegador enviada para {user.email}')
            except Exception as e:
                logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao enviar notificação no navegador: {e}', exc_info=True)
            
            # 2. Mensagem WhatsApp (se habilitado)
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
                        return
                    
                    # ✅ CORREÇÃO: Usar api_url e api_key da instância diretamente
                    # Se não tiver, buscar EvolutionConnection como fallback
                    base_url = instance.api_url
                    api_key = instance.api_key
                    
                    if not base_url or not api_key:
                        # Fallback: buscar EvolutionConnection
                        from apps.connections.models import EvolutionConnection
                        connection = EvolutionConnection.objects.filter(
                            tenant=task.tenant,
                            is_active=True
                        ).first()
                        
                        if connection:
                            base_url = connection.base_url
                            api_key = connection.api_key
                        else:
                            logger.warning(f'⚠️ [TASK NOTIFICATIONS] Nenhuma conexão Evolution configurada para tenant {task.tenant_id}')
                            return
                    
                    if not base_url or not api_key:
                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] API URL ou API Key não configurados')
                        return
                    
                    # ✅ CORREÇÃO: Normalizar telefone do usuário (formato E.164)
                    phone = user.phone.strip()
                    if not phone.startswith('+'):
                        # Assumir Brasil se não tiver código do país
                        if phone.startswith('55'):
                            phone = f'+{phone}'
                        else:
                            # Remover caracteres não numéricos e adicionar +55
                            phone_clean = ''.join(filter(str.isdigit, phone))
                            if phone_clean.startswith('55'):
                                phone = f'+{phone_clean}'
                            else:
                                phone = f'+55{phone_clean}'
                    
                    # Formatar mensagem
                    due_time = task.due_date.strftime('%d/%m/%Y às %H:%M')
                    message_text = f"🔔 *Lembrete de Tarefa*\n\n"
                    message_text += f"*{task.title}*\n\n"
                    message_text += f"📅 Data/Hora: {due_time}\n"
                    if task.department:
                        message_text += f"🏢 Departamento: {task.department.name}\n"
                    if task.notes:
                        message_text += f"\n📝 Notas: {task.notes[:200]}"
                    
                    # ✅ CORREÇÃO: Usar instance_name da instância e base_url normalizado
                    base_url = base_url.rstrip('/')
                    url = f"{base_url}/message/sendText/{instance.instance_name}"
                    headers = {
                        'apikey': api_key,
                        'Content-Type': 'application/json'
                    }
                    payload = {
                        'number': phone,
                        'text': message_text
                    }
                    
                    logger.info(f'📤 [TASK NOTIFICATIONS] Enviando WhatsApp para {phone} (usuário: {user.email})')
                    logger.info(f'   URL: {url}')
                    logger.info(f'   Instância: {instance.instance_name}')
                    
                    response = requests.post(url, json=payload, headers=headers, timeout=10)
                    if response.status_code in [200, 201]:
                        logger.info(f'✅ [TASK NOTIFICATIONS] WhatsApp enviado com sucesso para {phone}')
                    else:
                        logger.warning(f'⚠️ [TASK NOTIFICATIONS] Falha ao enviar WhatsApp: {response.status_code} - {response.text}')
                        logger.warning(f'   Payload: {payload}')
                        
                except Exception as e:
                    logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao enviar WhatsApp: {e}', exc_info=True)
        
        # Iniciar thread de recuperação
        recovery_thread = threading.Thread(target=recover_active_campaigns, daemon=True)
        recovery_thread.start()
        
        # ✅ NOVO: Iniciar thread de verificação de campanhas agendadas
        scheduler_thread = threading.Thread(target=check_scheduled_campaigns, daemon=True)
        scheduler_thread.start()
        logger.info("✅ [APPS] Verificador de campanhas agendadas iniciado")
