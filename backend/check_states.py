from apps.contacts.models import Contact
from django.db.models import Count

print('Total contatos:', Contact.objects.count())
contacts = Contact.objects.all()[:5]
for c in contacts:
    print(f'{c.name} | {c.phone} | Estado: {c.state}')

state_counts = Contact.objects.values('state').annotate(count=Count('id')).order_by('-count')
for item in state_counts:
    state_val = item['state'] if item['state'] else 'NULL'
    print(f'{state_val}: {item["count"]}')



