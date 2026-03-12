"""
Management command para verificar tarefas próximas e enviar notificações.

Roda em loop contínuo (similar ao engine de campanhas) e verifica tarefas que:
- Estão agendadas para os próximos 15 minutos
- Não foram notificadas ainda
- Não estão concluídas ou canceladas

Envia:
1. Notificação no navegador (via WebSocket/API)
2. Mensagem WhatsApp (se usuário tiver notify_whatsapp=True e telefone)

Uso:
    python manage.py check_task_notifications  # Roda em loop contínuo
    python manage.py check_task_notifications --run-once  # Executa uma vez e sai
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.contacts.models import Task
from apps.authn.models import User
from apps.notifications.models import WhatsAppInstance
from apps.notifications.services import send_whatsapp_notification, send_websocket_notification
from apps.connections.models import EvolutionConnection
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
import requests
import json
import time

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Verifica tarefas próximas e envia notificações'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes-before',
            type=int,
            default=15,
            help='Minutos antes do evento para enviar notificação (padrão: 15)'
        )
        parser.add_argument(
            '--run-once',
            action='store_true',
            help='Executa uma vez e sai (ao invés de rodar em loop)'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Intervalo entre verificações em segundos (padrão: 60)'
        )

    def handle(self, *args, **options):
        minutes_before = options['minutes_before']
        run_once = options['run_once']
        interval = options['interval']
        
        # ✅ LOG INICIAL FORÇADO (para debug no Railway)
        logger.info('🔔 [WORKER TASKS] ==========================================')
        logger.info('🔔 [WORKER TASKS] INICIANDO TASK NOTIFICATIONS')
        logger.info(f'⏰ Intervalo: {interval} segundos')
        logger.info(f'📅 Janela de notificação: {minutes_before} minutos antes')
        self.stdout.write(
            self.style.SUCCESS('🔔 [WORKER TASKS] Iniciando verificador de notificações de tarefas...')
        )
        
        if run_once:
            self._check_and_notify(minutes_before)
        else:
            # Loop contínuo (similar ao engine de campanhas)
            self.stdout.write(f'⏰ Intervalo: {interval} segundos')
            self.stdout.write(f'📅 Janela de notificação: {minutes_before} minutos antes')
            
            try:
                while True:
                    self._check_and_notify(minutes_before)
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING('\n⏹️ Verificador interrompido pelo usuário')
                )
            except Exception as e:
                logger.error(f'❌ Erro no loop principal: {e}', exc_info=True)
                self.stdout.write(self.style.ERROR(f'❌ Erro no loop principal: {e}'))
                raise
    
    def _check_and_notify(self, minutes_before):
        """Verifica e notifica tarefas"""
        now = timezone.now()
        
        # ✅ MELHORIA: Ampliar janela de notificação
        notification_window_start = now + timedelta(minutes=minutes_before - 5)
        notification_window_end = now + timedelta(minutes=minutes_before + 5)
        
        # ✅ NOVO: Verificar também tarefas que chegaram no momento exato
        exact_time_window_start = now - timedelta(minutes=5)
        exact_time_window_end = now + timedelta(minutes=1)
        
        logger.info(f'🔔 [TASK NOTIFICATIONS] Verificando lembretes (15min antes) entre {notification_window_start} e {notification_window_end}')
        logger.info(f'🔔 [TASK NOTIFICATIONS] Verificando compromissos chegando (momento exato) entre {exact_time_window_start} e {exact_time_window_end}')
        self.stdout.write(f'🔔 Verificando lembretes entre {notification_window_start.strftime("%H:%M:%S")} e {notification_window_end.strftime("%H:%M:%S")}')
        self.stdout.write(f'⏰ Verificando compromissos chegando entre {exact_time_window_start.strftime("%H:%M:%S")} e {exact_time_window_end.strftime("%H:%M:%S")}')
        
        # 1. Buscar tarefas para lembrete (15 minutos antes)
        tasks_reminder = Task.objects.filter(
            due_date__gte=notification_window_start,
            due_date__lte=notification_window_end,
            status__in=['pending', 'in_progress'],
            notification_sent=False
        ).exclude(
            status__in=['completed', 'cancelled']
        ).select_related('assigned_to', 'created_by', 'tenant', 'department')
        
        # 2. ✅ NOVO: Buscar tarefas que chegaram no momento exato
        tasks_exact_time = Task.objects.filter(
            due_date__gte=exact_time_window_start,
            due_date__lte=exact_time_window_end,
            status__in=['pending', 'in_progress']
        ).exclude(
            status__in=['completed', 'cancelled']
        ).select_related('assigned_to', 'created_by', 'tenant', 'department')
        
        total_reminder = tasks_reminder.count()
        total_exact = tasks_exact_time.count()
        
        logger.info(f'📋 [TASK NOTIFICATIONS] Encontradas {total_reminder} tarefa(s) para lembrete (15min antes)')
        logger.info(f'📋 [TASK NOTIFICATIONS] Encontradas {total_exact} tarefa(s) chegando agora (momento exato)')
        self.stdout.write(f'📋 Encontradas {total_reminder} tarefa(s) para lembrete e {total_exact} chegando agora')
        
        # ✅ DEBUG: Listar todas as tarefas próximas (mesmo que já notificadas)
        all_upcoming = Task.objects.filter(
            due_date__gte=now,
            due_date__lte=now + timedelta(hours=24),
            status__in=['pending', 'in_progress']
        ).select_related('assigned_to', 'created_by', 'tenant', 'department').order_by('due_date')[:10]
        
        if all_upcoming.exists():
            logger.info(f'📅 [TASK NOTIFICATIONS] Próximas 10 tarefas nas próximas 24h:')
            for task in all_upcoming:
                logger.info(f'   - {task.title} ({task.tenant.name}): {task.due_date} | Notificada: {task.notification_sent} | Status: {task.status}')
        
        count_reminder = 0
        count_exact = 0
        
        # Processar lembretes (15 minutos antes)
        for task in tasks_reminder:
            try:
                task.refresh_from_db()
                if task.status in ['completed', 'cancelled']:
                    continue
                
                notification_sent = False
                
                # Notificar usuário atribuído
                if task.assigned_to:
                    success = self._notify_user(task, task.assigned_to, is_reminder=True)
                    notification_sent = notification_sent or success
                
                # Notificar criador
                if task.created_by and task.created_by != task.assigned_to:
                    success = self._notify_user(task, task.created_by, is_reminder=True)
                    notification_sent = notification_sent or success
                
                # ✅ NOVO: Enviar notificações para contatos relacionados se notify_contacts estiver habilitado
                contacts_notified = False
                metadata = task.metadata or {}
                notify_contacts = metadata.get('notify_contacts', False)
                
                if notify_contacts and task.related_contacts.exists():
                    try:
                        from apps.contacts.services.task_notifications import send_task_reminder_to_contacts
                        contact_message_ids = send_task_reminder_to_contacts(task, is_15min_before=True)
                        if contact_message_ids:
                            contacts_notified = True
                            logger.info(f'✅ [TASK NOTIFICATIONS] {len(contact_message_ids)} lembrete(s) enviado(s) para contatos relacionados da tarefa {task.id}')
                    except Exception as e:
                        logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao enviar lembretes para contatos: {e}', exc_info=True)
                
                # ✅ MELHORIA: Só marcar como notificada se pelo menos uma notificação foi enviada
                if notification_sent or contacts_notified:
                    task.notification_sent = True
                    task.save(update_fields=['notification_sent'])
                    count_reminder += 1
                else:
                    logger.warning(f'⚠️ [TASK NOTIFICATIONS] Nenhuma notificação foi enviada com sucesso para tarefa {task.id}, mantendo notification_sent=False para retry')
                
            except Exception as e:
                logger.error(f'❌ Erro ao notificar tarefa {task.id}: {e}', exc_info=True)
                self.stdout.write(self.style.ERROR(f'Erro ao notificar tarefa {task.id}: {e}'))
        
        # ✅ NOVO: Processar notificações no momento exato do compromisso
        for task in tasks_exact_time:
            try:
                task.refresh_from_db()
                if task.status in ['completed', 'cancelled']:
                    continue
                
                # Verificar se já passou do horário
                if task.due_date < now - timedelta(minutes=1):
                    continue
                
                notification_sent = False
                
                # Notificar usuário atribuído
                if task.assigned_to:
                    success = self._notify_user(task, task.assigned_to, is_reminder=False)
                    notification_sent = notification_sent or success
                
                # Notificar criador
                if task.created_by and task.created_by != task.assigned_to:
                    success = self._notify_user(task, task.created_by, is_reminder=False)
                    notification_sent = notification_sent or success
                
                # ✅ NOVO: Enviar notificações para contatos relacionados se notify_contacts estiver habilitado
                contacts_notified = False
                metadata = task.metadata or {}
                notify_contacts = metadata.get('notify_contacts', False)
                
                if notify_contacts and task.related_contacts.exists():
                    try:
                        from apps.contacts.services.task_notifications import send_task_reminder_to_contacts
                        contact_message_ids = send_task_reminder_to_contacts(task, is_15min_before=False)
                        if contact_message_ids:
                            contacts_notified = True
                            logger.info(f'✅ [TASK NOTIFICATIONS] {len(contact_message_ids)} notificação(ões) de compromisso enviada(s) para contatos relacionados da tarefa {task.id}')
                    except Exception as e:
                        logger.error(f'❌ [TASK NOTIFICATIONS] Erro ao enviar notificações de compromisso para contatos: {e}', exc_info=True)
                
                if notification_sent or contacts_notified:
                    count_exact += 1
                
            except Exception as e:
                logger.error(f'❌ Erro ao notificar compromisso chegando para tarefa {task.id}: {e}', exc_info=True)
                self.stdout.write(self.style.ERROR(f'Erro ao notificar compromisso chegando para tarefa {task.id}: {e}'))
        
        if count_reminder > 0 or count_exact > 0:
            self.stdout.write(self.style.SUCCESS(f'✅ {count_reminder} lembrete(s) e {count_exact} notificação(ões) de compromisso enviadas'))
    
    def _notify_user(self, task: Task, user: User, is_reminder=True):
        """
        Notifica um usuário sobre uma tarefa.
        
        Args:
            task: Tarefa a ser notificada
            user: Usuário a ser notificado
            is_reminder: Se True, é lembrete (15min antes). Se False, é notificação no momento exato.
        
        Returns:
            bool: True se pelo menos uma notificação foi enviada com sucesso
        """
        notification_sent = False
        
        # 1. Notificação no navegador (via WebSocket)
        if self._send_browser_notification(task, user, is_reminder):
            notification_sent = True
        
        # 2. Mensagem WhatsApp (se habilitado)
        if user.notify_whatsapp and user.phone:
            if self._send_whatsapp_notification(task, user, is_reminder):
                notification_sent = True
        
        return notification_sent
    
    def _send_browser_notification(self, task: Task, user: User, is_reminder=True):
        """Envia notificação no navegador via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning('⚠️ Channel layer não configurado, pulando notificação no navegador')
                return False
            
            # ✅ MELHORIA: Mensagem diferente para lembrete vs compromisso chegando
            due_time = task.due_date.strftime('%d/%m/%Y às %H:%M')
            if is_reminder:
                message = f"🔔 Lembrete: {task.title}\n📅 {due_time}"
                notification_type = "lembrete"
            else:
                message = f"⏰ Compromisso chegando: {task.title}\n📅 {due_time}"
                notification_type = "compromisso"
            
            # Enviar via WebSocket para o grupo do tenant (usuários conectados receberão)
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
            # Também enviar pelo canal do chat para quem está na tela do chat receber (toast + sino)
            try:
                from apps.chat.utils.websocket import send_user_notification
                send_user_notification(
                    str(task.tenant_id),
                    str(user.id),
                    'task_reminder',
                    {
                        'task_id': str(task.id),
                        'title': task.title,
                        'message': message,
                        'due_date': task.due_date.isoformat(),
                    },
                )
            except Exception as send_err:
                logger.warning('⚠️ send_user_notification (task_reminder) falhou: %s', send_err)

            logger.info(f'✅ Notificação no navegador ({notification_type}) enviada para {user.email}')
            return True
            
        except Exception as e:
            logger.error(f'❌ Erro ao enviar notificação no navegador: {e}', exc_info=True)
            return False
    
    def _send_whatsapp_notification(self, task: Task, user: User, is_reminder=True):
        """Envia notificação via WhatsApp usando services.py"""
        try:
            # ✅ MELHORIA: Formatar mensagem com mais contexto
            due_time = task.due_date.strftime('%d/%m/%Y às %H:%M')
            
            if is_reminder:
                message = f"🔔 *Lembrete de Tarefa*\n\n"
            else:
                message = f"⏰ *Compromisso Agendado*\n\n"
            
            message += f"*{task.title}*\n\n"
            
            # Adicionar descrição se houver
            if task.description:
                desc = task.description[:300].replace('\n', ' ')
                message += f"{desc}\n\n"
            
            message += f"📅 *Data/Hora:* {due_time}\n"
            
            # Adicionar departamento
            if task.department:
                message += f"🏢 *Departamento:* {task.department.name}\n"
            
            # Adicionar prioridade
            priority_display = dict(task.PRIORITY_CHOICES).get(task.priority, task.priority)
            priority_emoji = {
                'low': '🟢',
                'medium': '🟡',
                'high': '🟠',
                'urgent': '🔴'
            }.get(task.priority, '⚪')
            message += f"{priority_emoji} *Prioridade:* {priority_display}\n"
            
            # Adicionar contatos relacionados se houver
            if task.related_contacts.exists():
                contacts = task.related_contacts.all()[:3]
                contact_names = ', '.join([c.name for c in contacts])
                if task.related_contacts.count() > 3:
                    contact_names += f" e mais {task.related_contacts.count() - 3}"
                message += f"👤 *Contatos:* {contact_names}\n"
            
            message += f"\nAcesse o sistema para mais detalhes."
            
            # ✅ USAR services.py (já tem retry e normalização de telefone)
            success = send_whatsapp_notification(user, message)
            if success:
                logger.info(f'✅ [TASK NOTIFICATION] WhatsApp enviado para {user.email}')
            else:
                logger.warning(f'⚠️ [TASK NOTIFICATION] Falha ao enviar WhatsApp para {user.email}')
            
            return success
                
        except Exception as e:
            logger.error(f'❌ [TASK NOTIFICATION] Erro ao enviar WhatsApp para {user.email}: {e}', exc_info=True)
            return False

