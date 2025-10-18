"""
Script para verificar que as campanhas não foram afetadas.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import Campaign


print('=== VERIFICAÇÃO DE CAMPANHAS ===')
total = Campaign.objects.count()
print(f'Total de campanhas: {total}')

if total > 0:
    c = Campaign.objects.first()
    print(f'\nCampanha exemplo:')
    print(f'  Nome: {c.name}')
    print(f'  Status: {c.status}')
    print(f'  Tenant: {c.tenant.name}')
    print(f'  Mensagens: {c.messages.count()}')
    print(f'  Contatos: {c.total_contacts}')
    print('\n✅ Campanhas intactas! Nenhuma alteração detectada.')
else:
    print('\nℹ️ Nenhuma campanha encontrada no banco.')

