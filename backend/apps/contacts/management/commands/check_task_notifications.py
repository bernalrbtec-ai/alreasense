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
        notification_window_start = now + timedelta(minutes=minutes_before - 1)
        notification_window_end = now + timedelta(minutes=minutes_before + 1)
        
        logger.info(f'🔔 [TASK NOTIFICATIONS] Verificando tarefas entre {notification_window_start} e {notification_window_end}')
        self.stdout.write(f'🔔 Verificando tarefas entre {notification_window_start} e {notification_window_end}')
        
        # Buscar tarefas que estão no período de notificação
        tasks_to_notify = Task.objects.filter(
            due_date__gte=notification_window_start,
            due_date__lte=notification_window_end,
            status__in=['pending', 'in_progress'],
            notification_sent=False
        ).select_related('assigned_to', 'created_by', 'tenant', 'department')
        
        total_tasks = tasks_to_notify.count()
        logger.info(f'📋 [TASK NOTIFICATIONS] Encontradas {total_tasks} tarefa(s) para notificar')
        self.stdout.write(f'📋 Encontradas {total_tasks} tarefa(s) para notificar')
        
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
        
        count = 0
        for task in tasks_to_notify:
            try:
                # Notificar usuário atribuído (se houver)
                if task.assigned_to:
                    self._notify_user(task, task.assigned_to)
                
                # Notificar criador (se diferente do atribuído)
                if task.created_by and task.created_by != task.assigned_to:
                    self._notify_user(task, task.created_by)
                
                # Marcar como notificada
                task.notification_sent = True
                task.save(update_fields=['notification_sent'])
                count += 1
                
            except Exception as e:
                logger.error(f'❌ Erro ao notificar tarefa {task.id}: {e}', exc_info=True)
                self.stdout.write(self.style.ERROR(f'Erro ao notificar tarefa {task.id}: {e}'))
        
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f'✅ {count} tarefa(s) notificada(s)'))
    
    def _notify_user(self, task: Task, user: User):
        """Notifica um usuário sobre uma tarefa"""
        # 1. Notificação no navegador (via WebSocket)
        self._send_browser_notification(task, user)
        
        # 2. Mensagem WhatsApp (se habilitado)
        if user.notify_whatsapp and user.phone:
            self._send_whatsapp_notification(task, user)
    
    def _send_browser_notification(self, task: Task, user: User):
        """Envia notificação no navegador via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning('⚠️ Channel layer não configurado, pulando notificação no navegador')
                return
            
            # Formatar mensagem
            due_time = task.due_date.strftime('%d/%m/%Y às %H:%M')
            message = f"🔔 Lembrete: {task.title}\n📅 {due_time}"
            
            # Enviar via WebSocket para o grupo do tenant (usuários conectados receberão)
            async_to_sync(channel_layer.group_send)(
                f"tenant_{task.tenant_id}",
                {
                    'type': 'task_notification',
                    'task_id': str(task.id),
                    'title': task.title,
                    'message': message,
                    'due_date': task.due_date.isoformat(),
                    'user_id': str(user.id),  # Filtrar no frontend para mostrar apenas para o usuário correto
                }
            )
            
            logger.info(f'✅ Notificação no navegador enviada para {user.email}')
            
        except Exception as e:
            logger.error(f'❌ Erro ao enviar notificação no navegador: {e}', exc_info=True)
    
    def _send_whatsapp_notification(self, task: Task, user: User):
        """Envia notificação via WhatsApp"""
        try:
            # Buscar instância WhatsApp ativa do tenant
            instance = WhatsAppInstance.objects.filter(
                tenant=task.tenant,
                is_active=True,
                status='active'
            ).first()
            
            if not instance:
                logger.warning(f'⚠️ Nenhuma instância WhatsApp ativa para tenant {task.tenant.name}')
                return
            
            # Buscar servidor Evolution
            evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
            
            if not evolution_server and not instance.api_url:
                logger.error('❌ Configuração da Evolution API não encontrada')
                return
            
            # Preparar URL e credenciais
            base_url = (instance.api_url or evolution_server.base_url).rstrip('/')
            api_key = instance.api_key or evolution_server.api_key
            
            # Formatar mensagem
            due_time = task.due_date.strftime('%d/%m/%Y às %H:%M')
            message = f"🔔 *Lembrete de Tarefa*\n\n"
            message += f"*{task.title}*\n\n"
            if task.description:
                message += f"{task.description[:200]}\n\n"
            message += f"📅 Data/Hora: {due_time}\n"
            if task.department:
                message += f"🏢 Departamento: {task.department.name}\n"
            message += f"\nAcesse o sistema para mais detalhes."
            
            # Normalizar telefone do usuário
            phone = user.phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            if not phone.startswith('55'):
                # Assumir Brasil se não tiver código do país
                phone = f'55{phone}'
            
            # Enviar mensagem
            response = requests.post(
                f"{base_url}/message/sendText/{instance.instance_name}",
                headers={'apikey': api_key},
                json={
                    'number': phone,
                    'text': message
                },
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f'✅ WhatsApp enviado para {user.email} ({phone})')
            else:
                logger.error(f'❌ Erro ao enviar WhatsApp: {response.status_code} - {response.text}')
                
        except Exception as e:
            logger.error(f'❌ Erro ao enviar WhatsApp para {user.email}: {e}', exc_info=True)

