from apps.contacts.models import Contact
from django.db.models import Count

print('🔍 Verificando estados dos contatos...')
print(f'📊 Total de contatos no sistema: {Contact.objects.count()}')

# Primeiros 10 contatos
contacts = Contact.objects.all()[:10]
print(f'📊 Primeiros 10 contatos:')
for contact in contacts:
    print(f'  • {contact.name} | {contact.phone} | Estado: "{contact.state}" | DDD: {contact.phone[:2] if contact.phone else "N/A"}')

# Contagem por estado
print(f'📊 Contagem por estado:')
state_counts = Contact.objects.values('state').annotate(count=Count('id')).order_by('-count')
for item in state_counts:
    print(f'  • {item["state"] or "NULL"}: {item["count"]} contatos')

# Verificar se há contatos sem estado
no_state = Contact.objects.filter(state__isnull=True).count()
print(f'⚠️ Contatos sem estado: {no_state}')


