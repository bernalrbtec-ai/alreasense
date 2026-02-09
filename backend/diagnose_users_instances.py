"""
Script de diagnóstico para verificar por que usuários e instâncias não aparecem
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.authn.models import User
from apps.notifications.models import WhatsAppInstance
from apps.tenancy.models import Tenant
from apps.common.cache_manager import CacheManager

print("\n" + "="*60)
print("DIAGNOSTICO: Usuarios e Instancias")
print("="*60)

# 1. Verificar todos os tenants
print("\n1. TENANTS:")
tenants = Tenant.objects.all()
print(f"   Total de tenants: {tenants.count()}")
for tenant in tenants:
    print(f"   - {tenant.name} (ID: {tenant.id}, Status: {tenant.status})")

# 2. Verificar todos os usuários
print("\n2. USUARIOS:")
users = User.objects.select_related('tenant').all()
print(f"   Total de usuários: {users.count()}")
for user in users:
    tenant_name = user.tenant.name if user.tenant else "SEM TENANT"
    print(f"   - {user.email} (ID: {user.id}, Tenant: {tenant_name}, Ativo: {user.is_active})")

# 3. Verificar usuários por tenant
print("\n3. USUARIOS POR TENANT:")
for tenant in tenants:
    tenant_users = User.objects.filter(tenant=tenant)
    print(f"   {tenant.name}: {tenant_users.count()} usuários")
    for user in tenant_users:
        print(f"      - {user.email} (ID: {user.id}, Ativo: {user.is_active})")

# 4. Verificar todas as instâncias
print("\n4. INSTANCIAS WHATSAPP:")
instances = WhatsAppInstance.objects.select_related('tenant', 'created_by').all()
print(f"   Total de instâncias: {instances.count()}")
for instance in instances:
    tenant_name = instance.tenant.name if instance.tenant else "SEM TENANT"
    created_by = instance.created_by.email if instance.created_by else "N/A"
    print(f"   - {instance.friendly_name} (ID: {instance.id}, Tenant: {tenant_name}, Criado por: {created_by})")

# 5. Verificar instâncias por tenant
print("\n5. INSTANCIAS POR TENANT:")
for tenant in tenants:
    tenant_instances = WhatsAppInstance.objects.filter(tenant=tenant)
    print(f"   {tenant.name}: {tenant_instances.count()} instâncias")
    for instance in tenant_instances:
        print(f"      - {instance.friendly_name} (ID: {instance.id})")

# 6. Verificar cache de usuários
print("\n6. CACHE DE USUARIOS:")
for tenant in tenants:
    cache_key = CacheManager.make_key(
        CacheManager.PREFIX_USER,
        'tenant',
        tenant_id=tenant.id
    )
    cached_ids = CacheManager.get_or_set(
        cache_key,
        lambda: list(User.objects.filter(tenant=tenant).values_list('id', flat=True)),
        ttl=CacheManager.TTL_MINUTE * 5
    )
    print(f"   {tenant.name}: Cache key = {cache_key}")
    print(f"      IDs no cache: {cached_ids}")
    print(f"      Total no banco: {User.objects.filter(tenant=tenant).count()}")

# 7. Verificar cache de instâncias
print("\n7. CACHE DE INSTANCIAS:")
for tenant in tenants:
    cache_key = CacheManager.make_key(
        CacheManager.PREFIX_INSTANCE,
        'tenant',
        tenant_id=tenant.id
    )
    cached_ids = CacheManager.get_or_set(
        cache_key,
        lambda: list(WhatsAppInstance.objects.filter(tenant=tenant).values_list('id', flat=True)),
        ttl=CacheManager.TTL_MINUTE * 2
    )
    print(f"   {tenant.name}: Cache key = {cache_key}")
    print(f"      IDs no cache: {cached_ids}")
    print(f"      Total no banco: {WhatsAppInstance.objects.filter(tenant=tenant).count()}")

# 8. Limpar cache se necessário
print("\n8. LIMPAR CACHE:")
print("   Para limpar cache manualmente, execute:")
print("   CacheManager.invalidate_pattern('user:*')")
print("   CacheManager.invalidate_pattern('instance:*')")

print("\n" + "="*60)
print("Diagnostico concluido!")
print("="*60)
