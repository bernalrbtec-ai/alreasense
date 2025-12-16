"""
Management command para verificar timeouts do menu de boas-vindas.
Executar: python manage.py check_welcome_menu_timeouts

✅ Task Periódica: Roda em loop infinito (a cada 1 minuto)
Verifica conversas com menu pendente e:
- Envia lembrete após 5 minutos de inatividade
- Fecha conversa após 10 minutos de inatividade

Para rodar em produção, usar supervisor ou systemd:
[program:welcome_menu_timeouts]
command=python manage.py check_welcome_menu_timeouts
directory=/app
autostart=true
autorestart=true
"""
import logging
import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from apps.chat.models_welcome_menu import WelcomeMenuConfig, WelcomeMenuTimeout
from apps.chat.services.welcome_menu_service import WelcomeMenuService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Verifica timeouts do menu de boas-vindas periodicamente.
    Envia lembretes e fecha conversas inativas automaticamente.
    """
    
    help = 'Verifica timeouts do menu de boas-vindas (roda a cada 1 minuto)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Executa uma vez e sai (para testes)',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Intervalo em segundos entre verificações (padrão: 60)',
        )

    def handle(self, *args, **options):
        run_once = options['once']
        interval = options['interval']
        
        self.stdout.write(self.style.SUCCESS('⏰ [WELCOME MENU TIMEOUTS] Iniciando verificação de timeouts...'))
        self.stdout.write(f'   📌 Intervalo: {interval} segundos')
        self.stdout.write(f'   📌 Modo: {"Uma vez" if run_once else "Loop contínuo"}')
        self.stdout.write('')
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                self.stdout.write(f'\n🔄 [ITERAÇÃO {iteration}] {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}')
                
                try:
                    self.check_timeouts()
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'❌ Erro ao verificar timeouts: {e}'))
                    logger.error(f"❌ [WELCOME MENU TIMEOUTS] Erro ao verificar timeouts: {e}", exc_info=True)
                
                if run_once:
                    self.stdout.write(self.style.SUCCESS('✅ Verificação única concluída'))
                    break
                
                # Aguardar próxima verificação
                self.stdout.write(f'⏸️  Aguardando {interval} segundos...')
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n⚠️ Interrompido pelo usuário'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro fatal: {e}'))
            logger.error(f"❌ [WELCOME MENU TIMEOUTS] Erro fatal: {e}", exc_info=True)
            raise
    
    def check_timeouts(self):
        """
        Verifica todos os timeouts ativos e processa conforme necessário.
        """
        now = timezone.now()
        
        # Buscar todos os timeouts ativos
        timeouts = WelcomeMenuTimeout.objects.filter(
            is_active=True
        ).select_related('conversation', 'conversation__tenant').order_by('menu_sent_at')
        
        total_timeouts = timeouts.count()
        self.stdout.write(f'📊 Total de timeouts ativos: {total_timeouts}')
        
        if total_timeouts == 0:
            self.stdout.write('   ℹ️  Nenhum timeout ativo')
            return
        
        processed = 0
        reminders_sent = 0
        conversations_closed = 0
        errors = 0
        
        for timeout in timeouts:
            try:
                # Buscar configuração do tenant
                try:
                    config = WelcomeMenuConfig.objects.get(
                        tenant=timeout.conversation.tenant,
                        inactivity_timeout_enabled=True
                    )
                except WelcomeMenuConfig.DoesNotExist:
                    # Sem configuração ou timeout desabilitado, desativar timeout
                    timeout.is_active = False
                    timeout.save(update_fields=['is_active', 'updated_at'])
                    self.stdout.write(f'   ⏭️  Timeout desativado (config não encontrada): {timeout.conversation.contact_name or timeout.conversation.contact_phone}')
                    continue
                
                # Calcular tempo decorrido
                elapsed_minutes = (now - timeout.menu_sent_at).total_seconds() / 60
                
                # Verificar se já passou o tempo de fechamento automático
                if elapsed_minutes >= config.auto_close_minutes:
                    self.stdout.write(f'   🔒 Fechando conversa: {timeout.conversation.contact_name or timeout.conversation.contact_phone} ({elapsed_minutes:.1f} min)')
                    
                    # Fechar conversa automaticamente
                    success = WelcomeMenuService._close_conversation(timeout.conversation)
                    if success:
                        timeout.is_active = False
                        timeout.save(update_fields=['is_active', 'updated_at'])
                        conversations_closed += 1
                        logger.info(f"🔒 [TIMEOUT] Conversa {timeout.conversation.id} fechada por inatividade ({elapsed_minutes:.1f} min)")
                    else:
                        self.stdout.write(self.style.WARNING(f'   ⚠️  Erro ao fechar conversa {timeout.conversation.id}'))
                        errors += 1
                
                # Verificar se já passou o tempo do primeiro lembrete
                elif elapsed_minutes >= config.first_reminder_minutes and not timeout.reminder_sent:
                    self.stdout.write(f'   ⏰ Enviando lembrete: {timeout.conversation.contact_name or timeout.conversation.contact_phone} ({elapsed_minutes:.1f} min)')
                    
                    # Enviar lembrete
                    success = WelcomeMenuService._send_inactivity_reminder(timeout.conversation, config)
                    if success:
                        timeout.reminder_sent = True
                        timeout.reminder_sent_at = now
                        timeout.save(update_fields=['reminder_sent', 'reminder_sent_at', 'updated_at'])
                        reminders_sent += 1
                        logger.info(f"⏰ [TIMEOUT] Lembrete enviado para conversa {timeout.conversation.id} ({elapsed_minutes:.1f} min)")
                    else:
                        self.stdout.write(self.style.WARNING(f'   ⚠️  Erro ao enviar lembrete {timeout.conversation.id}'))
                        errors += 1
                
                else:
                    # Timeout ainda não atingiu nenhum limite
                    minutes_to_reminder = config.first_reminder_minutes - elapsed_minutes
                    minutes_to_close = config.auto_close_minutes - elapsed_minutes
                    self.stdout.write(
                        f'   ⏳ {timeout.conversation.contact_name or timeout.conversation.contact_phone}: '
                        f'{elapsed_minutes:.1f} min decorridos '
                        f'(lembrete em {minutes_to_reminder:.1f} min, fechamento em {minutes_to_close:.1f} min)'
                    )
                
                processed += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Erro ao processar timeout {timeout.id}: {e}'))
                logger.error(f"❌ [WELCOME MENU TIMEOUTS] Erro ao processar timeout {timeout.id}: {e}", exc_info=True)
                errors += 1
        
        # Resumo
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✅ Verificação concluída:'))
        self.stdout.write(f'   📊 Processados: {processed}')
        self.stdout.write(f'   ⏰ Lembretes enviados: {reminders_sent}')
        self.stdout.write(f'   🔒 Conversas fechadas: {conversations_closed}')
        if errors > 0:
            self.stdout.write(self.style.WARNING(f'   ⚠️  Erros: {errors}'))

