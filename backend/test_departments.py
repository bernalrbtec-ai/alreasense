"""
Script para testar se departamentos e campo departments estão funcionando.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.authn.models import Department, User


print('=== DEPARTAMENTOS ===')
for d in Department.objects.select_related('tenant').all()[:10]:
    print(f'{d.tenant.name}: {d.name} ({d.color})')

print('\n=== USUÁRIOS ===')
u = User.objects.first()
if u:
    print(f'User: {u.email}')
    print(f'Tenant: {u.tenant.name}')
    print(f'Role: {u.role}')
    print(f'Departments: {[d.name for d in u.departments.all()]}')
else:
    print('Nenhum usuário encontrado')

