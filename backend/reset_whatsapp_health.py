#!/usr/bin/env python
"""
Script para resetar o health score das instâncias do WhatsApp
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import WhatsAppInstance

def reset_whatsapp_health():
    """Reseta o health score de todas as instâncias do WhatsApp"""
    try:
        print("🔧 RESETANDO HEALTH SCORE DAS INSTÂNCIAS WHATSAPP...")
        
        # Buscar todas as instâncias
        instances = WhatsAppInstance.objects.all()
        
        print(f"📊 INSTÂNCIAS ENCONTRADAS: {instances.count()}")
        
        if instances.count() == 0:
            print("❌ Nenhuma instância encontrada!")
            return False
        
        # Mostrar status atual
        print("\n📋 STATUS ATUAL DAS INSTÂNCIAS:")
        for instance in instances:
            print(f"   • {instance.instance_name}: health={instance.health_score}")
        
        # Resetar health score para 100
        print("\n🔄 Resetando health score para 100...")
        updated_count = instances.update(health_score=100)
        
        print(f"✅ {updated_count} instâncias atualizadas!")
        
        # Verificar resultado
        print("\n📋 STATUS APÓS RESET:")
        for instance in WhatsAppInstance.objects.all():
            print(f"   • {instance.instance_name}: health={instance.health_score}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO durante reset: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 RESET DO HEALTH SCORE DAS INSTÂNCIAS WHATSAPP")
    print("=" * 60)
    
    # Confirmação
    confirm = input("\n⚠️ Isso vai resetar o health score de todas as instâncias para 100!\nDeseja continuar? (sim/não): ").lower()
    
    if confirm in ['sim', 's', 'yes', 'y']:
        success = reset_whatsapp_health()
        if success:
            print("\n✅ Health score resetado com sucesso!")
        else:
            print("\n❌ Erro durante o reset!")
    else:
        print("\n❌ Operação cancelada pelo usuário.")
