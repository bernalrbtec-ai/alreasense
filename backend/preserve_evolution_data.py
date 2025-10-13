#!/usr/bin/env python
"""
Script para preservar dados da Evolution API durante deploys.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import WhatsAppInstance
from apps.connections.models import EvolutionConnection

def preserve_evolution_data():
    """Preserva dados da Evolution API durante deploys."""
    print("🔒 PRESERVING EVOLUTION API DATA")
    print("=" * 50)
    
    # Verificar instâncias WhatsApp
    instances = WhatsAppInstance.objects.all()
    print(f"📱 WhatsApp Instances: {instances.count()}")
    
    for instance in instances:
        print(f"   - {instance.friendly_name}: {instance.instance_name}")
        print(f"     API URL: {instance.api_url}")
        print(f"     Status: {instance.status}")
    
    # Verificar conexões Evolution
    connections = EvolutionConnection.objects.all()
    print(f"🔗 Evolution Connections: {connections.count()}")
    
    for connection in connections:
        print(f"   - {connection.name}: {connection.base_url}")
        print(f"     Status: {connection.status}")
    
    print("=" * 50)
    print("✅ Evolution API data preserved!")

if __name__ == '__main__':
    preserve_evolution_data()
