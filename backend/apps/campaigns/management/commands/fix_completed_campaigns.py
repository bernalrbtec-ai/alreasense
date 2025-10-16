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
        
        # Buscar campanhas ativas/running que não têm contatos pendentes
        campaigns_to_fix = []
        
        active_campaigns = Campaign.objects.filter(status__in=['active', 'running'])
        
        for campaign in active_campaigns:
            pending_contacts = CampaignContact.objects.filter(
                campaign=campaign, 
                status='pending'
            ).count()
            
            if pending_contacts == 0:
                campaigns_to_fix.append(campaign)
                self.stdout.write(
                    f"📋 Campanha '{campaign.name}' (ID: {campaign.id}) - "
                    f"Status: {campaign.status}, Contatos pendentes: {pending_contacts}"
                )
        
        if not campaigns_to_fix:
            self.stdout.write(
                self.style.SUCCESS("✅ Todas as campanhas estão com status correto!")
            )
            return
        
        self.stdout.write(f"\n📊 Encontradas {len(campaigns_to_fix)} campanhas para corrigir:")
        
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
