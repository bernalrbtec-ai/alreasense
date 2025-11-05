#!/usr/bin/env python
"""
Script de debug para verificar conversas e departamentos.
"""
import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.chat.models import Conversation
from apps.notifications.models import WhatsAppInstance
from apps.authn.models import Department

print("=" * 80)
print("🔍 DEBUG: Verificando Conversas e Departamentos")
print("=" * 80)

# Buscar todas as conversas recentes
conversations = Conversation.objects.select_related('department', 'tenant').order_by('-created_at')[:10]

print(f"\n📋 Últimas {len(conversations)} conversas:")
for conv in conversations:
    dept_name = conv.department.name if conv.department else "NENHUM (Inbox)"
    print(f"  - {conv.contact_name or conv.contact_phone}")
    print(f"    ID: {conv.id}")
    print(f"    Departamento: {dept_name} (ID: {conv.department_id or 'None'})")
    print(f"    Status: {conv.status}")
    print(f"    Instance: {conv.instance_name}")
    print(f"    Criada em: {conv.created_at}")
    print()

# Buscar instâncias WhatsApp
print("\n📱 Instâncias WhatsApp:")
instances = WhatsAppInstance.objects.select_related('default_department', 'tenant').filter(is_active=True, status='active')
for inst in instances:
    dept_name = inst.default_department.name if inst.default_department else "NENHUM"
    print(f"  - {inst.friendly_name} ({inst.instance_name})")
    print(f"    Default Department: {dept_name} (ID: {inst.default_department_id or 'None'})")
    print(f"    Tenant: {inst.tenant.name}")
    print()

# Buscar departamentos
print("\n🏢 Departamentos:")
departments = Department.objects.all()[:10]
for dept in departments:
    print(f"  - {dept.name} (ID: {dept.id})")
    print(f"    Tenant: {dept.tenant.name}")
    print()

print("=" * 80)

