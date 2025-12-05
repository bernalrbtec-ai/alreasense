"""
Management command para verificar e enviar notificações diárias e lembretes de agenda.

Roda em loop contínuo e verifica:
- Resumos diários (daily_summary) - enviar no horário configurado
- Lembretes de agenda (agenda_reminder) - enviar no horário configurado

Uso:
    python manage.py check_daily_notifications  # Roda em loop contínuo
    python manage.py check_daily_notifications --run-once  # Executa uma vez e sai
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, time as dt_time
from apps.notifications.models import UserNotificationPreferences
from apps.contacts.models import Task
from apps.notifications.services import send_whatsapp_notification, send_websocket_notification, get_greeting, format_weekday_pt
from apps.authn.models import User
import logging
import time

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Verifica e envia notificações diárias e lembretes de agenda'

    def add_arguments(self, parser):
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
        run_once = options['run_once']
        interval = options['interval']
        
        logger.info('🔔 [DAILY NOTIFICATIONS] ==========================================')
        logger.info('🔔 [DAILY NOTIFICATIONS] INICIANDO DAILY NOTIFICATIONS WORKER')
        logger.info(f'⏰ Intervalo: {interval} segundos')
        self.stdout.write(
            self.style.SUCCESS('🔔 [DAILY NOTIFICATIONS] Iniciando verificador de notificações diárias...')
        )
        
        if run_once:
            self._check_and_send()
        else:
            try:
                while True:
                    self._check_and_send()
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING('\n⏹️ Verificador interrompido pelo usuário')
                )
            except Exception as e:
                logger.error(f'❌ Erro no loop principal: {e}', exc_info=True)
                self.stdout.write(self.style.ERROR(f'❌ Erro no loop principal: {e}'))
                raise
    
    def _check_and_send(self):
        """Verifica e envia notificações diárias"""
        now = timezone.localtime(timezone.now())
        current_time = now.time()
        current_date = now.date()
        
        logger.info(f'🔔 [DAILY NOTIFICATIONS] Verificando notificações para {current_time.strftime("%H:%M:%S")}')
        
        # 1. Verificar resumos diários (daily_summary)
        self._check_daily_summaries(current_time, current_date)
        
        # 2. Verificar lembretes de agenda (agenda_reminder)
        self._check_agenda_reminders(current_time, current_date)
    
    def _check_daily_summaries(self, current_time: dt_time, current_date):
        """Verifica e envia resumos diários"""
        # Buscar usuários com daily_summary habilitado
        preferences = UserNotificationPreferences.objects.filter(
            daily_summary_enabled=True,
            daily_summary_time__isnull=False
        ).select_related('user', 'tenant')
        
        logger.info(f'🔍 [DAILY SUMMARY] Buscando preferências: {preferences.count()} usuários com daily_summary habilitado')
        
        count_sent = 0
        count_skipped = 0
        count_not_in_window = 0
        
        for pref in preferences:
            try:
                user = pref.user
                summary_time = pref.daily_summary_time
                
                logger.debug(f'   🔍 [DAILY SUMMARY] Verificando {user.email}: horário configurado={summary_time}, hora atual={current_time}')
                
                # Verificar se já foi enviado hoje
                if pref.last_daily_summary_sent_date == current_date:
                    logger.info(f'   ⏭️ [DAILY SUMMARY] Pulando {user.email} - já enviado hoje ({pref.last_daily_summary_sent_date})')
                    count_skipped += 1
                    continue
                
                # ✅ CORREÇÃO: Verificar se está no horário (com margem de ±2 minutos)
                # Melhorar cálculo para evitar erros com horários próximos de 00:00
                if summary_time.minute >= 2:
                    time_window_start = dt_time(summary_time.hour, summary_time.minute - 2)
                elif summary_time.hour > 0:
                    time_window_start = dt_time(summary_time.hour - 1, 58 + summary_time.minute)
                else:
                    # Se for 00:00 ou 00:01, usar 23:58 ou 23:59 do dia anterior
                    time_window_start = dt_time(23, 58 + summary_time.minute)
                
                # Calcular fim da janela (pode passar de 23:59)
                if summary_time.minute <= 57:
                    time_window_end = dt_time(summary_time.hour, summary_time.minute + 2)
                elif summary_time.hour < 23:
                    time_window_end = dt_time(summary_time.hour + 1, summary_time.minute - 58)
                else:
                    # Se for 23:58 ou 23:59, usar 00:00 ou 00:01 do dia seguinte
                    time_window_end = dt_time(0, summary_time.minute - 58)
                
                logger.debug(f'   ⏰ [DAILY SUMMARY] Janela de tempo: {time_window_start} <= {current_time} <= {time_window_end}')
                
                # ✅ CORREÇÃO: Verificar se está na janela (considerar que pode passar de 23:59)
                is_in_window = False
                if time_window_start <= time_window_end:
                    # Janela normal (não passa de meia-noite)
                    is_in_window = time_window_start <= current_time <= time_window_end
                else:
                    # Janela que passa de meia-noite (ex: 23:58 - 00:02)
                    is_in_window = current_time >= time_window_start or current_time <= time_window_end
                
                if not is_in_window:
                    logger.debug(f'   ⏭️ [DAILY SUMMARY] {user.email} não está na janela de tempo')
                    count_not_in_window += 1
                    continue
                
                logger.info(f'   ✅ [DAILY SUMMARY] {user.email} está na janela de tempo! Enviando resumo...')
                
                # Enviar resumo diário
                success = self._send_daily_summary(user, pref, current_date)
                if success:
                    count_sent += 1
                    # Atualizar data do último envio
                    pref.last_daily_summary_sent_date = current_date
                    pref.save(update_fields=['last_daily_summary_sent_date'])
                
            except Exception as e:
                logger.error(f'❌ [DAILY SUMMARY] Erro ao processar {pref.user.email}: {e}', exc_info=True)
        
        if count_sent > 0:
            logger.info(f'✅ [DAILY SUMMARY] {count_sent} resumo(s) enviado(s), {count_skipped} pulado(s), {count_not_in_window} fora da janela')
            self.stdout.write(self.style.SUCCESS(f'✅ {count_sent} resumo(s) diário(s) enviado(s)'))
        elif preferences.count() > 0:
            logger.info(f'ℹ️ [DAILY SUMMARY] Nenhum resumo enviado: {count_skipped} já enviados hoje, {count_not_in_window} fora da janela de tempo')
    
    def _check_agenda_reminders(self, current_time: dt_time, current_date):
        """Verifica e envia lembretes de agenda"""
        # Buscar usuários com agenda_reminder habilitado
        preferences = UserNotificationPreferences.objects.filter(
            agenda_reminder_enabled=True,
            agenda_reminder_time__isnull=False
        ).select_related('user', 'tenant')
        
        logger.info(f'🔍 [AGENDA REMINDER] Buscando preferências: {preferences.count()} usuários com agenda_reminder habilitado')
        
        count_sent = 0
        count_not_in_window = 0
        
        for pref in preferences:
            try:
                user = pref.user
                reminder_time = pref.agenda_reminder_time
                
                logger.debug(f'   🔍 [AGENDA REMINDER] Verificando {user.email}: horário configurado={reminder_time}, hora atual={current_time}')
                
                # ✅ CORREÇÃO: Verificar se está no horário (com margem de ±2 minutos)
                # Melhorar cálculo para evitar erros com horários próximos de 00:00
                if reminder_time.minute >= 2:
                    time_window_start = dt_time(reminder_time.hour, reminder_time.minute - 2)
                elif reminder_time.hour > 0:
                    time_window_start = dt_time(reminder_time.hour - 1, 58 + reminder_time.minute)
                else:
                    # Se for 00:00 ou 00:01, usar 23:58 ou 23:59 do dia anterior
                    time_window_start = dt_time(23, 58 + reminder_time.minute)
                
                # Calcular fim da janela (pode passar de 23:59)
                if reminder_time.minute <= 57:
                    time_window_end = dt_time(reminder_time.hour, reminder_time.minute + 2)
                elif reminder_time.hour < 23:
                    time_window_end = dt_time(reminder_time.hour + 1, reminder_time.minute - 58)
                else:
                    # Se for 23:58 ou 23:59, usar 00:00 ou 00:01 do dia seguinte
                    time_window_end = dt_time(0, reminder_time.minute - 58)
                
                logger.debug(f'   ⏰ [AGENDA REMINDER] Janela de tempo: {time_window_start} <= {current_time} <= {time_window_end}')
                
                # ✅ CORREÇÃO: Verificar se está na janela (considerar que pode passar de 23:59)
                is_in_window = False
                if time_window_start <= time_window_end:
                    # Janela normal (não passa de meia-noite)
                    is_in_window = time_window_start <= current_time <= time_window_end
                else:
                    # Janela que passa de meia-noite (ex: 23:58 - 00:02)
                    is_in_window = current_time >= time_window_start or current_time <= time_window_end
                
                if not is_in_window:
                    logger.debug(f'   ⏭️ [AGENDA REMINDER] {user.email} não está na janela de tempo')
                    count_not_in_window += 1
                    continue
                
                logger.info(f'   ✅ [AGENDA REMINDER] {user.email} está na janela de tempo! Enviando lembrete...')
                
                # Enviar lembrete de agenda
                success = self._send_agenda_reminder(user, pref, current_date)
                if success:
                    count_sent += 1
                
            except Exception as e:
                logger.error(f'❌ [AGENDA REMINDER] Erro ao processar {pref.user.email}: {e}', exc_info=True)
        
        if count_sent > 0:
            logger.info(f'✅ [AGENDA REMINDER] {count_sent} lembrete(s) de agenda enviado(s), {count_not_in_window} fora da janela')
            self.stdout.write(self.style.SUCCESS(f'✅ {count_sent} lembrete(s) de agenda enviado(s)'))
        elif preferences.count() > 0:
            logger.info(f'ℹ️ [AGENDA REMINDER] Nenhum lembrete enviado: {count_not_in_window} fora da janela de tempo')
    
    def _send_daily_summary(self, user: User, pref: UserNotificationPreferences, current_date):
        """Envia resumo diário para o usuário"""
        try:
            # Buscar tarefas do dia
            tasks_today = Task.objects.filter(
                tenant=user.tenant,
                assigned_to=user,
                due_date__date=current_date,
                status__in=['pending', 'in_progress']
            ).select_related('department')
            
            tasks_pending = tasks_today.filter(status='pending')
            tasks_in_progress = tasks_today.filter(status='in_progress')
            tasks_overdue = Task.objects.filter(
                tenant=user.tenant,
                assigned_to=user,
                due_date__lt=timezone.now(),
                status__in=['pending', 'in_progress']
            ).count()
            
            greeting = get_greeting()
            weekday = format_weekday_pt(current_date)
            
            # Formatar mensagem
            message = f"{greeting}, {user.first_name or user.email}!\n\n"
            message += f"📅 *Resumo do Dia - {weekday}*\n\n"
            
            if tasks_pending.exists() or tasks_in_progress.exists() or tasks_overdue > 0:
                message += f"📋 *Tarefas de Hoje:*\n"
                message += f"   • Pendentes: {tasks_pending.count()}\n"
                message += f"   • Em progresso: {tasks_in_progress.count()}\n"
                if tasks_overdue > 0:
                    message += f"   ⚠️ Atrasadas: {tasks_overdue}\n"
                message += f"\n"
            else:
                message += f"✅ Nenhuma tarefa agendada para hoje!\n\n"
            
            message += f"Tenha um ótimo dia! 🚀"
            
            # Enviar via WhatsApp se habilitado
            if pref.notify_via_whatsapp and user.notify_whatsapp and user.phone:
                success = send_whatsapp_notification(user, message)
                if success:
                    logger.info(f'✅ [DAILY SUMMARY] Resumo enviado para {user.email}')
                    return True
            
            # Enviar via WebSocket se habilitado
            if pref.notify_via_websocket:
                data = {
                    'type': 'daily_summary',
                    'date': current_date.isoformat(),
                    'tasks_pending': tasks_pending.count(),
                    'tasks_in_progress': tasks_in_progress.count(),
                    'tasks_overdue': tasks_overdue
                }
                send_websocket_notification(user, 'daily_summary', data)
                logger.info(f'✅ [DAILY SUMMARY] Resumo WebSocket enviado para {user.email}')
                return True
            
            return False
            
        except Exception as e:
            logger.error(f'❌ [DAILY SUMMARY] Erro ao enviar resumo para {user.email}: {e}', exc_info=True)
            return False
    
    def _send_agenda_reminder(self, user: User, pref: UserNotificationPreferences, current_date):
        """Envia lembrete de agenda para o usuário"""
        try:
            # Buscar tarefas próximas (próximas 24 horas)
            now = timezone.now()
            next_24h = now + timedelta(hours=24)
            
            upcoming_tasks = Task.objects.filter(
                tenant=user.tenant,
                assigned_to=user,
                due_date__gte=now,
                due_date__lte=next_24h,
                status__in=['pending', 'in_progress']
            ).select_related('department').order_by('due_date')[:5]
            
            greeting = get_greeting()
            
            # Formatar mensagem
            message = f"{greeting}, {user.first_name or user.email}!\n\n"
            message += f"📅 *Lembrete de Agenda*\n\n"
            
            if upcoming_tasks.exists():
                message += f"Você tem {upcoming_tasks.count()} compromisso(s) nas próximas 24h:\n\n"
                for task in upcoming_tasks:
                    due_time = timezone.localtime(task.due_date).strftime('%d/%m às %H:%M')
                    message += f"• {task.title} - {due_time}\n"
            else:
                message += f"✅ Nenhum compromisso agendado para as próximas 24h!\n"
            
            # Enviar via WhatsApp se habilitado
            if pref.notify_via_whatsapp and user.notify_whatsapp and user.phone:
                success = send_whatsapp_notification(user, message)
                if success:
                    logger.info(f'✅ [AGENDA REMINDER] Lembrete enviado para {user.email}')
                    return True
            
            # Enviar via WebSocket se habilitado
            if pref.notify_via_websocket:
                data = {
                    'type': 'agenda_reminder',
                    'upcoming_tasks': [
                        {
                            'id': str(task.id),
                            'title': task.title,
                            'due_date': task.due_date.isoformat()
                        }
                        for task in upcoming_tasks
                    ]
                }
                send_websocket_notification(user, 'agenda_reminder', data)
                logger.info(f'✅ [AGENDA REMINDER] Lembrete WebSocket enviado para {user.email}')
                return True
            
            return False
            
        except Exception as e:
            logger.error(f'❌ [AGENDA REMINDER] Erro ao enviar lembrete para {user.email}: {e}', exc_info=True)
            return False

