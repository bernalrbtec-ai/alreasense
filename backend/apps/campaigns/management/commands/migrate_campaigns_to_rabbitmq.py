"""
Comando para migrar campanhas existentes para o sistema RabbitMQ
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.campaigns.models import Campaign, CampaignContact, CampaignLog
from apps.campaigns.rabbitmq_consumer import rabbitmq_consumer


class Command(BaseCommand):
    help = 'Migra campanhas existentes para o sistema RabbitMQ'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas simula a migração sem fazer alterações',
        )
        parser.add_argument(
            '--campaign-id',
            type=str,
            help='ID específico da campanha para migrar',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Força migração mesmo de campanhas problemáticas',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        campaign_id = options.get('campaign_id')
        force = options.get('force', False)
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🧪 MODO SIMULAÇÃO - Nenhuma alteração será feita')
            )
        
        self.stdout.write(
            self.style.SUCCESS('🔄 Iniciando migração de campanhas para RabbitMQ...')
        )
        
        try:
            # Filtros base
            campaigns_query = Campaign.objects.all()
            
            if campaign_id:
                campaigns_query = campaigns_query.filter(id=campaign_id)
            
            # Campanhas que precisam de migração
            campaigns_to_migrate = campaigns_query.filter(
                status__in=['running', 'paused']
            )
            
            total_campaigns = campaigns_to_migrate.count()
            
            if total_campaigns == 0:
                self.stdout.write(
                    self.style.SUCCESS('✅ Nenhuma campanha precisa de migração!')
                )
                return
            
            self.stdout.write(
                self.style.SUCCESS(f'📊 {total_campaigns} campanhas para migrar')
            )
            
            # Verificar problemas antes da migração
            if not force:
                self._check_migration_issues(campaigns_to_migrate)
            
            # Migrar campanhas
            migrated_count = 0
            failed_count = 0
            
            for campaign in campaigns_to_migrate:
                try:
                    success = self._migrate_campaign(campaign, dry_run)
                    if success:
                        migrated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'✅ {campaign.name} migrada com sucesso')
                        )
                    else:
                        failed_count += 1
                        self.stdout.write(
                            self.style.ERROR(f'❌ Falha ao migrar {campaign.name}')
                        )
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'❌ Erro ao migrar {campaign.name}: {e}')
                    )
            
            # Resumo
            self.stdout.write('\n📊 Resumo da migração:')
            self.stdout.write(f'  ✅ Migradas: {migrated_count}')
            self.stdout.write(f'  ❌ Falharam: {failed_count}')
            self.stdout.write(f'  📊 Total: {total_campaigns}')
            
            if not dry_run and migrated_count > 0:
                self.stdout.write(
                    self.style.SUCCESS('🎉 Migração concluída! Agora inicie o RabbitMQ Consumer.')
                )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro durante migração: {e}')
            )
            raise

    def _check_migration_issues(self, campaigns):
        """Verifica problemas que podem impedir migração"""
        self.stdout.write('\n🔍 Verificando problemas de migração...')
        
        issues_found = False
        
        for campaign in campaigns:
            # Verificar contatos pendentes
            pending_contacts = CampaignContact.objects.filter(
                campaign=campaign,
                status__in=['pending', 'sending']
            ).count()
            
            if pending_contacts == 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️ {campaign.name}: Sem contatos pendentes (status: {campaign.status})'
                    )
                )
                issues_found = True
            
            # Verificar instâncias
            if not campaign.instances.exists():
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ {campaign.name}: Sem instâncias configuradas'
                    )
                )
                issues_found = True
            
            # Verificar mensagens
            if not campaign.messages.exists():
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ {campaign.name}: Sem mensagens configuradas'
                    )
                )
                issues_found = True
        
        if issues_found:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️ Problemas encontrados! Use --force para migrar mesmo assim.'
                )
            )

    def _migrate_campaign(self, campaign, dry_run=False):
        """Migra uma campanha específica"""
        try:
            # Verificar se campanha pode ser migrada
            if not self._can_migrate_campaign(campaign):
                return False
            
            if dry_run:
                self.stdout.write(f'  🧪 [SIMULAÇÃO] Migrando {campaign.name}...')
                return True
            
            # Migrar campanha
            with transaction.atomic():
                # Atualizar status se necessário
                if campaign.status == 'paused':
                    # Manter pausada, mas preparar para RabbitMQ
                    self.stdout.write(f'  ⏸️ Campanha {campaign.name} será mantida pausada')
                elif campaign.status == 'running':
                    # Pausar temporariamente para migração
                    campaign.status = 'paused'
                    campaign.save(update_fields=['status'])
                    
                    # Log da migração
                    CampaignLog.log_campaign_state_change(
                        campaign=campaign,
                        old_status='running',
                        new_status='paused',
                        reason='Migração para RabbitMQ'
                    )
                    
                    self.stdout.write(f'  ⏸️ Campanha {campaign.name} pausada para migração')
                
                # Preparar dados para RabbitMQ
                self._prepare_campaign_for_rabbitmq(campaign)
                
                return True
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Erro ao migrar {campaign.name}: {e}')
            )
            return False

    def _can_migrate_campaign(self, campaign):
        """Verifica se campanha pode ser migrada"""
        # Verificar contatos
        if not CampaignContact.objects.filter(campaign=campaign).exists():
            self.stdout.write(f'  ❌ {campaign.name}: Sem contatos')
            return False
        
        # Verificar instâncias
        if not campaign.instances.exists():
            self.stdout.write(f'  ❌ {campaign.name}: Sem instâncias')
            return False
        
        # Verificar mensagens
        if not campaign.messages.exists():
            self.stdout.write(f'  ❌ {campaign.name}: Sem mensagens')
            return False
        
        return True

    def _prepare_campaign_for_rabbitmq(self, campaign):
        """Prepara campanha para o sistema RabbitMQ"""
        # Resetar contatos que estavam sendo processados
        CampaignContact.objects.filter(
            campaign=campaign,
            status='sending'
        ).update(status='pending')
        
        # Log da preparação
        CampaignLog.log_info(
            campaign=campaign,
            message='Campanha preparada para migração RabbitMQ',
            details={
                'migration_date': timezone.now().isoformat(),
                'total_contacts': CampaignContact.objects.filter(campaign=campaign).count(),
                'pending_contacts': CampaignContact.objects.filter(
                    campaign=campaign,
                    status='pending'
                ).count()
            }
        )
        
        self.stdout.write(f'  ✅ {campaign.name} preparada para RabbitMQ')
