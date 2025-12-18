#!/usr/bin/env python
"""
Script de diagnóstico para mensagens rápidas (Quick Replies).
Verifica por que as mensagens rápidas não estão sendo buscadas.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.chat.models import QuickReply
from apps.tenancy.models import Tenant
from django.core.cache import cache

print("=" * 80)
print("🔍 DIAGNÓSTICO: Mensagens Rápidas (Quick Replies)")
print("=" * 80)

# 1. Verificar total de mensagens rápidas
total = QuickReply.objects.count()
ativas = QuickReply.objects.filter(is_active=True).count()
inativas = QuickReply.objects.filter(is_active=False).count()

print(f"\n📊 ESTATÍSTICAS GERAIS:")
print(f"   Total: {total}")
print(f"   Ativas (is_active=True): {ativas}")
print(f"   Inativas (is_active=False): {inativas}")

if total == 0:
    print("\n⚠️  PROBLEMA: Nenhuma mensagem rápida cadastrada no banco!")
    print("   Solução: Cadastre mensagens rápidas através da interface ou API.")
    sys.exit(0)

# 2. Verificar por tenant
print(f"\n📋 POR TENANT:")
tenants = Tenant.objects.all()
for tenant in tenants:
    total_tenant = QuickReply.objects.filter(tenant=tenant).count()
    ativas_tenant = QuickReply.objects.filter(tenant=tenant, is_active=True).count()
    inativas_tenant = QuickReply.objects.filter(tenant=tenant, is_active=False).count()
    
    print(f"\n   Tenant: {tenant.name} (ID: {tenant.id})")
    print(f"      Total: {total_tenant}")
    print(f"      Ativas: {ativas_tenant}")
    print(f"      Inativas: {inativas_tenant}")
    
    if total_tenant > 0:
        # Mostrar algumas mensagens
        print(f"\n      Exemplos:")
        for qr in QuickReply.objects.filter(tenant=tenant)[:3]:
            print(f"         - {qr.title} (is_active={qr.is_active}, use_count={qr.use_count})")

# 3. Verificar cache
print(f"\n💾 CACHE:")
cache_keys = []
for tenant in tenants:
    cache_key = f"quick_replies:tenant:{tenant.id}"
    cached_data = cache.get(cache_key)
    cache_keys.append((cache_key, cached_data))
    
    if cached_data:
        print(f"   ✅ {cache_key}: Cache encontrado")
        if isinstance(cached_data, dict):
            count = cached_data.get('count', 0)
            print(f"      Count: {count}")
    else:
        print(f"   ❌ {cache_key}: Cache vazio ou expirado")

# 4. Verificar se há mensagens com is_active=False que deveriam estar ativas
print(f"\n🔍 ANÁLISE:")
if inativas > 0:
    print(f"   ⚠️  Encontradas {inativas} mensagens rápidas com is_active=False")
    print(f"   💡 O endpoint filtra apenas is_active=True, então essas não aparecerão!")
    print(f"\n   Mensagens inativas:")
    for qr in QuickReply.objects.filter(is_active=False)[:5]:
        print(f"      - {qr.title} (Tenant: {qr.tenant.name})")

# 5. Verificar estrutura do modelo
print(f"\n📐 ESTRUTURA DO MODELO:")
print(f"   Campo is_active: default=True (deve estar ativo por padrão)")
print(f"   Campo tenant: obrigatório (ForeignKey)")
print(f"   Campo created_by: opcional (ForeignKey, pode ser NULL)")

# 6. Verificar possíveis problemas
print(f"\n🐛 POSSÍVEIS PROBLEMAS:")
problemas = []

if total == 0:
    problemas.append("❌ Nenhuma mensagem rápida cadastrada")
elif ativas == 0:
    problemas.append("❌ Todas as mensagens estão com is_active=False")
    problemas.append("   Solução: Atualizar is_active=True nas mensagens ou remover filtro")
else:
    print(f"   ✅ Há {ativas} mensagens ativas no banco")

# Verificar se há problema com tenant
if total > 0:
    qr_sem_tenant = QuickReply.objects.filter(tenant__isnull=True).count()
    if qr_sem_tenant > 0:
        problemas.append(f"❌ {qr_sem_tenant} mensagens sem tenant (não devem existir)")

# Verificar cache
cache_vazio = all(cached is None for _, cached in cache_keys)
if cache_vazio and ativas > 0:
    print(f"   ⚠️  Cache vazio (normal se nunca foi acessado ou expirou)")
    print(f"   💡 O cache será preenchido na próxima requisição")

if problemas:
    print("\n   PROBLEMAS ENCONTRADOS:")
    for problema in problemas:
        print(f"   {problema}")
else:
    print("   ✅ Nenhum problema óbvio encontrado")
    print("   💡 Verifique:")
    print("      1. Se o usuário está autenticado")
    print("      2. Se o tenant do usuário corresponde ao tenant das mensagens")
    print("      3. Se há erros nos logs do servidor")
    print("      4. Se o endpoint está sendo chamado corretamente (/api/chat/quick-replies/)")

print("\n" + "=" * 80)

