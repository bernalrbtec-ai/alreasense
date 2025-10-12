"""Lista todas as campanhas"""
import os, sys, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import Campaign

print("\n" + "="*80)
print("📋 TODAS AS CAMPANHAS")
print("="*80 + "\n")

for c in Campaign.objects.all().order_by('-created_at'):
    print(f"📤 {c.name}")
    print(f"   ID: {c.id}")
    print(f"   Status: {c.status}")
    print(f"   Contatos: {c.total_contacts}")
    print(f"   Enviadas: {c.messages_sent}")
    print(f"   Entregues: {c.messages_delivered}")
    print(f"   Falhas: {c.messages_failed}")
    print(f"   Criada: {c.created_at}")
    print(f"   Iniciada: {c.started_at}")
    print(f"   Concluída: {c.completed_at}")
    print()



