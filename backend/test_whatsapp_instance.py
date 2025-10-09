#!/usr/bin/env python
"""
Script para testar criação de instância WhatsApp localmente
"""
import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import WhatsAppInstance
from apps.tenancy.models import Tenant
from apps.authn.models import User

def test_whatsapp_instance():
    print("=" * 60)
    print("🧪 TESTE DE CRIAÇÃO DE INSTÂNCIA WHATSAPP")
    print("=" * 60)
    
    # 1. Buscar tenant e usuário
    try:
        tenant = Tenant.objects.first()
        user = User.objects.filter(is_superuser=True).first()
        
        if not tenant:
            print("❌ Nenhum tenant encontrado!")
            return
        
        if not user:
            print("❌ Nenhum usuário encontrado!")
            return
            
        print(f"✅ Tenant: {tenant.name}")
        print(f"✅ User: {user.email}")
        
    except Exception as e:
        print(f"❌ Erro ao buscar tenant/user: {e}")
        return
    
    # 2. Criar instância de teste
    print("\n" + "=" * 60)
    print("📝 CRIANDO INSTÂNCIA DE TESTE")
    print("=" * 60)
    
    try:
        import uuid
        
        instance = WhatsAppInstance.objects.create(
            tenant=tenant,
            friendly_name="Teste Local",
            instance_name=str(uuid.uuid4()),
            api_url="",  # Vazio para testar fallback
            created_by=user
        )
        
        print(f"✅ Instância criada: {instance.id}")
        print(f"   - Nome amigável: {instance.friendly_name}")
        print(f"   - Instance name: {instance.instance_name}")
        print(f"   - API URL: '{instance.api_url}' (vazio)")
        
    except Exception as e:
        print(f"❌ Erro ao criar instância: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. Verificar servidor Evolution cadastrado
    print("\n" + "=" * 60)
    print("🔍 VERIFICANDO SERVIDOR EVOLUTION CADASTRADO")
    print("=" * 60)
    
    from apps.connections.models import EvolutionConnection
    
    evolution_server = EvolutionConnection.objects.filter(
        tenant=tenant,
        is_active=True
    ).first()
    
    if evolution_server:
        print(f"✅ Servidor Evolution encontrado:")
        print(f"   - Nome: {evolution_server.name}")
        print(f"   - URL: {evolution_server.base_url}")
        print(f"   - API Key: {'CONFIGURADA' if evolution_server.api_key else 'NÃO CONFIGURADA'}")
        print(f"   - Status: {evolution_server.status}")
    else:
        print(f"❌ Nenhum servidor Evolution ativo encontrado!")
        print(f"   Configure um servidor em: Admin → Servidor de Instância")
    
    # 4. Testar generate_qr_code
    print("\n" + "=" * 60)
    print("🔍 TESTANDO generate_qr_code()")
    print("=" * 60)
    
    try:
        print(f"🔄 Chamando generate_qr_code()...")
        qr_code = instance.generate_qr_code()
        
        if qr_code:
            print(f"✅ QR Code gerado com sucesso!")
            print(f"   - Tamanho: {len(qr_code)} caracteres")
            print(f"   - API Key salva: {'SIM' if instance.api_key else 'NÃO'}")
            print(f"   - Connection state: {instance.connection_state}")
        else:
            print(f"❌ Falha ao gerar QR code")
            print(f"   - Last error: {instance.last_error}")
            
    except Exception as e:
        print(f"❌ Exceção ao gerar QR code: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Limpar instância de teste
    print("\n" + "=" * 60)
    print("🧹 LIMPANDO INSTÂNCIA DE TESTE")
    print("=" * 60)
    
    try:
        instance.delete()
        print("✅ Instância removida")
    except Exception as e:
        print(f"❌ Erro ao remover instância: {e}")
    
    print("\n" + "=" * 60)
    print("✅ TESTE CONCLUÍDO")
    print("=" * 60)

if __name__ == '__main__':
    test_whatsapp_instance()

