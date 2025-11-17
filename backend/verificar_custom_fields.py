"""
Script para verificar campos customizados salvos nos contatos

Uso:
    python manage.py shell < verificar_custom_fields.py
    ou
    python verificar_custom_fields.py
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.contacts.models import Contact
from django.db.models import Q

print("\n" + "="*60)
print("VERIFICAÇÃO DE CAMPOS CUSTOMIZADOS NOS CONTATOS")
print("="*60)

# Buscar contatos com custom_fields preenchidos
contacts_with_custom = Contact.objects.filter(
    custom_fields__isnull=False
).exclude(
    custom_fields={}
)

total = contacts_with_custom.count()

print(f"\n📊 Total de contatos com campos customizados: {total}")

if total > 0:
    print("\n" + "-"*60)
    print("PRIMEIROS 10 CONTATOS COM CUSTOM_FIELDS:")
    print("-"*60)
    
    for i, contact in enumerate(contacts_with_custom[:10], 1):
        print(f"\n{i}. {contact.name} ({contact.phone})")
        print(f"   Custom Fields: {contact.custom_fields}")
        
        # Mostrar cada campo customizado
        if contact.custom_fields:
            for key, value in contact.custom_fields.items():
                print(f"      - {key}: {value}")
    
    if total > 10:
        print(f"\n... e mais {total - 10} contatos")
    
    # Estatísticas
    print("\n" + "-"*60)
    print("ESTATÍSTICAS:")
    print("-"*60)
    
    # Contar campos customizados únicos
    all_custom_keys = set()
    for contact in contacts_with_custom:
        if contact.custom_fields:
            all_custom_keys.update(contact.custom_fields.keys())
    
    print(f"\n📋 Campos customizados encontrados: {len(all_custom_keys)}")
    for key in sorted(all_custom_keys):
        count = contacts_with_custom.filter(
            custom_fields__has_key=key
        ).count()
        print(f"   - {key}: {count} contatos")
    
    # Exemplo de query para buscar por campo customizado
    print("\n" + "-"*60)
    print("EXEMPLOS DE QUERIES:")
    print("-"*60)
    
    # Buscar contatos com campo "clinica"
    if 'clinica' in all_custom_keys:
        clinica_contacts = contacts_with_custom.filter(
            custom_fields__has_key='clinica'
        )
        print(f"\n🔍 Contatos com campo 'clinica': {clinica_contacts.count()}")
        
        # Mostrar alguns exemplos
        for contact in clinica_contacts[:3]:
            print(f"   - {contact.name}: {contact.custom_fields.get('clinica')}")
    
    # Buscar contatos com campo "valor"
    if 'valor' in all_custom_keys:
        valor_contacts = contacts_with_custom.filter(
            custom_fields__has_key='valor'
        )
        print(f"\n💰 Contatos com campo 'valor': {valor_contacts.count()}")
    
else:
    print("\n⚠️ Nenhum contato com campos customizados encontrado.")
    print("\n💡 Dica: Verifique se a importação foi feita corretamente.")
    print("   Os campos customizados são salvos no campo 'custom_fields' (JSONField).")

print("\n" + "="*60)
print("✅ VERIFICAÇÃO CONCLUÍDA")
print("="*60)

