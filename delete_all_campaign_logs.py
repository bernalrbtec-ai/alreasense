"""
Script para deletar TODOS os logs de TODAS as campanhas
Execute: python delete_all_campaign_logs.py
"""
import os
import sys
import django

# Configurar Django
sys.path.append('backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import CampaignLog


def delete_all_logs():
    """Deleta todos os logs de campanhas"""
    
    print("="*80)
    print("🗑️  DELETAR TODOS OS LOGS DE CAMPANHAS")
    print("="*80)
    
    try:
        # Contar logs antes
        total_logs = CampaignLog.objects.count()
        
        print(f"\n📊 Total de logs encontrados: {total_logs}")
        
        if total_logs == 0:
            print("✅ Nenhum log para deletar!")
            return
        
        # Confirmar
        print("\n⚠️  ATENÇÃO: Esta ação é IRREVERSÍVEL!")
        print(f"⚠️  Você está prestes a deletar {total_logs} logs de TODAS as campanhas")
        print(f"⚠️  de TODOS os clientes/tenants!")
        
        # Aceitar confirmação via argumento ou input
        if len(sys.argv) > 1 and sys.argv[1] == '--confirm':
            print("\n✅ Confirmação via argumento --confirm")
            confirm = "DELETAR TUDO"
        else:
            confirm = input("\n🔴 Digite 'DELETAR TUDO' para confirmar (exatamente assim): ").strip()
        
        if confirm != "DELETAR TUDO":
            print("\n❌ Operação cancelada!")
            print("   Você não digitou 'DELETAR TUDO' corretamente")
            print("   Ou use: python delete_all_campaign_logs.py --confirm")
            return
        
        # Deletar todos os logs
        print(f"\n🗑️  Deletando {total_logs} logs...")
        deleted_count, _ = CampaignLog.objects.all().delete()
        
        print("\n" + "="*80)
        print("✅ LOGS DELETADOS COM SUCESSO!")
        print("="*80)
        print(f"📊 Total deletado: {deleted_count} logs")
        print("📊 Logs restantes: 0")
        print("\n💡 Novos logs serão criados automaticamente nas próximas campanhas")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Erro ao deletar logs: {e}")
        import traceback
        print("\nTraceback completo:")
        traceback.print_exc()


if __name__ == '__main__':
    delete_all_logs()

