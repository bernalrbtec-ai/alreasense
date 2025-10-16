"""
Comando para corrigir campanhas que estão com status incorreto.
"""
from django.core.management.base import BaseCommand
from apps.campaigns.models import Campaign, CampaignContact


class Command(BaseCommand):
    help = 'Corrige status de campanhas que foram reiniciadas incorretamente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem executar as mudanças',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("🔍 Analisando campanhas com status incorreto...")
        
        # Buscar campanhas que podem precisar de correção
        campaigns_to_fix = []
        campaigns_paused_by_user = []
        
        # Campanhas 'running' sem contatos pendentes = devem ser marcadas como concluídas
        running_campaigns = Campaign.objects.filter(status='running')
        
        for campaign in running_campaigns:
            pending_contacts = CampaignContact.objects.filter(
                campaign=campaign, 
                status='pending'
            ).count()
            
            if pending_contacts == 0:
                campaigns_to_fix.append(campaign)
                self.stdout.write(
                    f"📋 Campanha '{campaign.name}' (ID: {campaign.id}) - "
                    f"Status: {campaign.status}, Contatos pendentes: {pending_contacts} - MARCADA PARA CONCLUÍDA"
                )
        
        # Campanhas 'paused' ou 'stopped' = foram pausadas pelo usuário (manter status)
        paused_campaigns = Campaign.objects.filter(status__in=['paused', 'stopped'])
        
        for campaign in paused_campaigns:
            pending_contacts = CampaignContact.objects.filter(
                campaign=campaign, 
                status='pending'
            ).count()
            
            campaigns_paused_by_user.append(campaign)
            self.stdout.write(
                f"⏸️ Campanha '{campaign.name}' (ID: {campaign.id}) - "
                f"Status: {campaign.status}, Contatos pendentes: {pending_contacts} - PAUSADA PELO USUÁRIO (manter status)"
            )
        
        self.stdout.write(f"\n📊 RESUMO:")
        self.stdout.write(f"  🔄 Campanhas para marcar como concluídas: {len(campaigns_to_fix)}")
        self.stdout.write(f"  ⏸️ Campanhas pausadas pelo usuário: {len(campaigns_paused_by_user)}")
        
        if not campaigns_to_fix:
            self.stdout.write(
                self.style.SUCCESS("\n✅ Todas as campanhas estão com status correto!")
            )
            return
        
        self.stdout.write(f"\n📋 Campanhas que serão marcadas como concluídas:")
        
        for campaign in campaigns_to_fix:
            self.stdout.write(f"  • {campaign.name} (ID: {campaign.id})")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n🔍 DRY RUN - Nenhuma alteração foi feita")
            )
            return
        
        # Confirmar antes de executar
        confirm = input("\n❓ Deseja corrigir estas campanhas? (y/N): ")
        if confirm.lower() != 'y':
            self.stdout.write("❌ Operação cancelada")
            return
        
        # Executar correções
        corrected_count = 0
        for campaign in campaigns_to_fix:
            try:
                # Marcar como concluída
                campaign.status = 'completed'
                campaign.save()
                corrected_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Campanha '{campaign.name}' marcada como concluída")
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Erro ao corrigir campanha '{campaign.name}': {e}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"\n🎉 {corrected_count} campanhas corrigidas com sucesso!")
        )
