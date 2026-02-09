"""
Script de diagnóstico: por que instance_friendly_name mostra UUID em vez do nome?

Investiga por que o lookup em WhatsAppInstance falha para algumas conversas.
Execute: python backend/diagnose_instance_friendly_name.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db.models import Q
from apps.chat.models import Conversation
from apps.notifications.models import WhatsAppInstance

# UUID que o usuário vê (da imagem)
TARGET_UUID = "05886c7f-783e-4c49-8af3-bbcb1cf59621"

print("\n" + "="*70)
print("DIAGNOSTICO: Por que instance_friendly_name mostra UUID?")
print("="*70)

# 1. Buscar conversas com esse instance_name
print(f"\n1. CONVERSAS com instance_name = '{TARGET_UUID}' ou similar:")
convs = Conversation.objects.filter(instance_name__icontains="05886c7f").order_by('-last_message_at')[:10]
print(f"   Encontradas: {convs.count()}")

for c in convs:
    print(f"\n   Conversa ID: {c.id}")
    print(f"   - instance_name (raw): repr={repr(c.instance_name)}")
    print(f"   - instance_name len: {len(c.instance_name) if c.instance_name else 0}")
    print(f"   - instance_name hex: {c.instance_name.encode() if c.instance_name else b''}")
    print(f"   - tenant_id: {c.tenant_id}")

# 2. Buscar WhatsAppInstance - exatamente como o serializer faz
print(f"\n2. LOOKUP WhatsAppInstance (mesmo que serializer):")
print(f"   Filtro: Q(instance_name='{TARGET_UUID}') | Q(evolution_instance_name='{TARGET_UUID}')")

wa_by_instance = WhatsAppInstance.objects.filter(instance_name=TARGET_UUID).first()
wa_by_evolution = WhatsAppInstance.objects.filter(evolution_instance_name=TARGET_UUID).first()
wa_by_either = WhatsAppInstance.objects.filter(
    Q(instance_name=TARGET_UUID) | Q(evolution_instance_name=TARGET_UUID)
).first()

print(f"\n   Por instance_name exato: {wa_by_instance.friendly_name if wa_by_instance else 'NAO ENCONTRADO'}")
print(f"   Por evolution_instance_name exato: {wa_by_evolution.friendly_name if wa_by_evolution else 'NAO ENCONTRADO'}")
print(f"   Por Q(instance_name | evolution): {wa_by_either.friendly_name if wa_by_either else 'NAO ENCONTRADO'}")

# 3. Listar TODAS as instâncias para comparar
print(f"\n3. TODAS as WhatsAppInstance (comparar instance_name/evolution):")
for wi in WhatsAppInstance.objects.all().values('id', 'friendly_name', 'instance_name', 'evolution_instance_name'):
    in_match = wi['instance_name'] == TARGET_UUID if wi['instance_name'] else False
    ev_match = wi['evolution_instance_name'] == TARGET_UUID if wi['evolution_instance_name'] else False
    match = " <-- MATCH" if (in_match or ev_match) else ""
    print(f"   {wi['friendly_name']}: instance_name={repr(wi['instance_name'])}, evolution={repr(wi['evolution_instance_name'])}{match}")

# 4. Verificar cache
print(f"\n4. CACHE:")
try:
    from django.core.cache import cache
    cache_key_old = f"instance_friendly_name:{TARGET_UUID}"
    cache_key_v2 = f"instance_friendly_name:v2:{TARGET_UUID}"
    cached_old = cache.get(cache_key_old)
    cached_v2 = cache.get(cache_key_v2)
    print(f"   Cache antigo (instance_friendly_name:{TARGET_UUID}): {repr(cached_old)}")
    print(f"   Cache v2 (instance_friendly_name:v2:{TARGET_UUID}): {repr(cached_v2)}")
    if cached_old or cached_v2:
        print("   --> Se cache tem UUID, o serializer retorna UUID ate expirar (5 min)")
except Exception as e:
    print(f"   Erro ao verificar cache: {e}")

# 5. Possíveis causas
print(f"\n5. POSSIVEIS CAUSAS (se lookup falhou):")
if not wa_by_either:
    print("   - WhatsAppInstance nao existe com esse UUID")
    print("   - instance_name/evolution_instance_name na tabela pode estar diferente (espacos, case)")
    print("   - Cache antigo com UUID (agurar 5 min ou limpar Redis)")
else:
    print("   - Lookup DEVERIA funcionar! Verifique cache ou se serializer esta sendo usado")

print("\n" + "="*70)
