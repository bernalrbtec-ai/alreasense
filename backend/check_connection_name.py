"""
Script rápido para verificar o nome da conexão
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.connections.models import EvolutionConnection
from apps.tenancy.models import Tenant

rbtec = Tenant.objects.get(name="RBTec Informática")
conn = EvolutionConnection.objects.filter(tenant=rbtec, is_active=True).first()

print(f"Nome da conexão: '{conn.name}'")
print(f"Base URL: {conn.base_url}")
print(f"API Key: {conn.api_key[:10]}...")

# A Evolution API precisa do nome da instância no path
# Formato correto: https://evo.rbtec.com.br/message/sendText/INSTANCE_NAME
print(f"\n⚠️  O campo 'name' está vazio!")
print(f"Você precisa cadastrar o nome da instância Evolution no banco.")
print(f"Qual é o nome da sua instância? (ex: 'rbtec', 'principal', etc)")

