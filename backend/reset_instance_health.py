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

from apps.connections.models import EvolutionConnection

def reset_instance_health():
    """Reseta o health score de todas as instâncias"""
    try:
        print("🔧 RESETANDO HEALTH SCORE DAS INSTÂNCIAS...")
        
        # Buscar todas as instâncias
        instances = EvolutionConnection.objects.all()
        
        print(f"📊 INSTÂNCIAS ENCONTRADAS: {instances.count()}")
        
        if instances.count() == 0:
            print("❌ Nenhuma instância encontrada!")
            return False
        
        # Mostrar status atual
        print("\n📋 STATUS ATUAL DAS INSTÂNCIAS:")
        for instance in instances:
            print(f"   • {instance.name}: status={instance.status}")
        
        # Resetar status para active
        print("\n🔄 Resetando status para active...")
        updated_count = instances.update(status='active')
        
        print(f"✅ {updated_count} instâncias atualizadas!")
        
        # Verificar resultado
        print("\n📋 STATUS APÓS RESET:")
        for instance in EvolutionConnection.objects.all():
            print(f"   • {instance.name}: status={instance.status}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO durante reset: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 RESET DO HEALTH SCORE DAS INSTÂNCIAS")
    print("=" * 60)
    
    # Confirmação
    confirm = input("\n⚠️ Isso vai resetar o status de todas as instâncias para 'active'!\nDeseja continuar? (sim/não): ").lower()
    
    if confirm in ['sim', 's', 'yes', 'y']:
        success = reset_instance_health()
        if success:
            print("\n✅ Health score resetado com sucesso!")
        else:
            print("\n❌ Erro durante o reset!")
    else:
        print("\n❌ Operação cancelada pelo usuário.")
