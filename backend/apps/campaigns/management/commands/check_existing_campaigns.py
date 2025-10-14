"""
Comando para verificar campanhas existentes no banco
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from apps.campaigns.models import Campaign, CampaignContact, CampaignLog


class Command(BaseCommand):
    help = 'Verifica campanhas existentes no banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='ID do tenant para filtrar campanhas',
        )
        parser.add_argument(
            '--status',
            type=str,
            help='Status das campanhas (draft, running, paused, completed)',
        )

    def handle(self, *args, **options):
        tenant_id = options.get('tenant_id')
        status_filter = options.get('status')
        
        self.stdout.write(
            self.style.SUCCESS('🔍 Verificando campanhas existentes...')
        )
        
        try:
            # Filtros base
            campaigns_query = Campaign.objects.all()
            
            if tenant_id:
                campaigns_query = campaigns_query.filter(tenant_id=tenant_id)
            
            if status_filter:
                campaigns_query = campaigns_query.filter(status=status_filter)
            
            # Estatísticas gerais
            total_campaigns = campaigns_query.count()
            
            self.stdout.write(
                self.style.SUCCESS(f'📊 Total de campanhas: {total_campaigns}')
            )
            
            if total_campaigns == 0:
                self.stdout.write(
                    self.style.WARNING('⚠️ Nenhuma campanha encontrada!')
                )
                return
            
            # Estatísticas por status
            status_stats = campaigns_query.values('status').annotate(
                count=Count('id')
            ).order_by('status')
            
            self.stdout.write('\n📈 Estatísticas por status:')
            for stat in status_stats:
                status = stat['status']
                count = stat['count']
                emoji = self._get_status_emoji(status)
                self.stdout.write(f'  {emoji} {status}: {count}')
            
            # Campanhas detalhadas
            self.stdout.write('\n📋 Detalhes das campanhas:')
            campaigns = campaigns_query.select_related('tenant').order_by('-created_at')
            
            for campaign in campaigns[:10]:  # Mostrar apenas as 10 mais recentes
                self._show_campaign_details(campaign)
            
            if total_campaigns > 10:
                self.stdout.write(
                    self.style.WARNING(f'... e mais {total_campaigns - 10} campanhas')
                )
            
            # Campanhas problemáticas
            self._check_problematic_campaigns(campaigns_query)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro ao verificar campanhas: {e}')
            )
            raise

    def _get_status_emoji(self, status):
        """Retorna emoji para status"""
        emojis = {
            'draft': '📝',
            'running': '🚀',
            'paused': '⏸️',
            'completed': '✅',
            'cancelled': '❌'
        }
        return emojis.get(status, '❓')

    def _show_campaign_details(self, campaign):
        """Mostra detalhes de uma campanha"""
        # Contatos da campanha
        total_contacts = CampaignContact.objects.filter(campaign=campaign).count()
        pending_contacts = CampaignContact.objects.filter(
            campaign=campaign,
            status__in=['pending', 'sending']
        ).count()
        
        # Logs da campanha
        total_logs = CampaignLog.objects.filter(campaign=campaign).count()
        error_logs = CampaignLog.objects.filter(
            campaign=campaign,
            severity='error'
        ).count()
        
        emoji = self._get_status_emoji(campaign.status)
        
        self.stdout.write(f'\n  {emoji} {campaign.name}')
        self.stdout.write(f'    ID: {campaign.id}')
        self.stdout.write(f'    Status: {campaign.status}')
        self.stdout.write(f'    Tenant: {campaign.tenant.name if campaign.tenant else "N/A"}')
        self.stdout.write(f'    Criada: {campaign.created_at.strftime("%d/%m/%Y %H:%M")}')
        self.stdout.write(f'    Contatos: {total_contacts} total, {pending_contacts} pendentes')
        self.stdout.write(f'    Mensagens: {campaign.messages_sent} enviadas, {campaign.messages_failed} falhas')
        self.stdout.write(f'    Logs: {total_logs} total, {error_logs} erros')
        
        if campaign.status == 'running':
            self.stdout.write(
                self.style.WARNING('    ⚠️ ATENÇÃO: Campanha rodando sem worker!')
            )

    def _check_problematic_campaigns(self, campaigns_query):
        """Verifica campanhas com problemas"""
        self.stdout.write('\n🚨 Verificando campanhas problemáticas...')
        
        # Campanhas rodando sem contatos pendentes
        running_no_pending = campaigns_query.filter(
            status='running'
        ).annotate(
            pending_count=Count(
                'campaign_contacts',
                filter=Q(campaign_contacts__status__in=['pending', 'sending'])
            )
        ).filter(pending_count=0)
        
        if running_no_pending.exists():
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️ {running_no_pending.count()} campanhas rodando sem contatos pendentes:'
                )
            )
            for campaign in running_no_pending:
                self.stdout.write(f'  - {campaign.name} (ID: {campaign.id})')
        
        # Campanhas com muitos erros
        high_error_campaigns = campaigns_query.annotate(
            error_count=Count(
                'campaignlog',
                filter=Q(campaignlog__severity='error')
            )
        ).filter(error_count__gte=10)
        
        if high_error_campaigns.exists():
            self.stdout.write(
                self.style.ERROR(
                    f'❌ {high_error_campaigns.count()} campanhas com muitos erros:'
                )
            )
            for campaign in high_error_campaigns:
                error_count = campaign.error_count
                self.stdout.write(f'  - {campaign.name}: {error_count} erros')
        
        # Campanhas antigas não finalizadas
        from django.utils import timezone
        from datetime import timedelta
        
        old_unfinished = campaigns_query.filter(
            status__in=['running', 'paused'],
            created_at__lt=timezone.now() - timedelta(days=7)
        )
        
        if old_unfinished.exists():
            self.stdout.write(
                self.style.WARNING(
                    f'⏰ {old_unfinished.count()} campanhas antigas não finalizadas:'
                )
            )
            for campaign in old_unfinished:
                days_old = (timezone.now() - campaign.created_at).days
                self.stdout.write(f'  - {campaign.name}: {days_old} dias')
        
        # Resumo
        total_problems = (
            running_no_pending.count() + 
            high_error_campaigns.count() + 
            old_unfinished.count()
        )
        
        if total_problems == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ Nenhuma campanha problemática encontrada!')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Total de problemas encontrados: {total_problems}')
            )
