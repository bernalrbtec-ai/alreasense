#!/usr/bin/env python
"""
Script para restaurar dados do Railway após deploy.
"""
import os
import django
import json
import glob

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import WhatsAppInstance
from apps.connections.models import EvolutionConnection
from apps.tenancy.models import Tenant
from apps.contacts.models import Contact
from apps.campaigns.models import Campaign
from apps.billing.models import Plan
from django.contrib.auth import get_user_model

User = get_user_model()

def restore_all_data():
    """Restaura todos os dados do backup mais recente."""
    print("🔄 RAILWAY DATA RESTORATION")
    print("=" * 60)
    
    # Find most recent backup file
    backup_files = glob.glob("/tmp/railway_backup_*.json")
    if not backup_files:
        print("❌ No backup files found!")
        return False
    
    latest_backup = max(backup_files, key=os.path.getctime)
    print(f"📁 Using backup: {latest_backup}")
    
    # Load backup data
    with open(latest_backup, 'r') as f:
        backup_data = json.load(f)
    
    print(f"📅 Backup timestamp: {backup_data['timestamp']}")
    
    # 1. Restore Tenants
    print("📊 Restoring Tenants...")
    for tenant_data in backup_data['tenants']:
        plan = Plan.objects.filter(slug=tenant_data['plan']).first() if tenant_data['plan'] else None
        tenant, created = Tenant.objects.get_or_create(
            id=tenant_data['id'],
            defaults={
                'name': tenant_data['name'],
                'current_plan': plan,
                'status': tenant_data['status'],
                'ui_access': tenant_data['ui_access'],
            }
        )
        if created:
            print(f"   ✅ Created tenant: {tenant.name}")
        else:
            print(f"   ⏭️ Tenant exists: {tenant.name}")
    
    # 2. Restore Users
    print("👤 Restoring Users...")
    for user_data in backup_data['users']:
        tenant = Tenant.objects.filter(id=user_data['tenant_id']).first() if user_data['tenant_id'] else None
        
        if not User.objects.filter(id=user_data['id']).exists():
            user = User.objects.create(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                is_staff=user_data['is_staff'],
                is_superuser=user_data['is_superuser'],
                tenant=tenant,
                role=user_data['role'],
            )
            print(f"   ✅ Created user: {user.email}")
        else:
            print(f"   ⏭️ User exists: {user_data['email']}")
    
    # 3. Restore WhatsApp Instances
    print("📱 Restoring WhatsApp Instances...")
    for instance_data in backup_data['whatsapp_instances']:
        tenant = Tenant.objects.filter(id=instance_data['tenant_id']).first() if instance_data['tenant_id'] else None
        
        instance, created = WhatsAppInstance.objects.get_or_create(
            id=instance_data['id'],
            defaults={
                'friendly_name': instance_data['friendly_name'],
                'instance_name': instance_data['instance_name'],
                'api_url': instance_data['api_url'],
                'api_key': instance_data['api_key'],
                'status': instance_data['status'],
                'tenant': tenant,
            }
        )
        if created:
            print(f"   ✅ Created WhatsApp instance: {instance.friendly_name}")
        else:
            print(f"   ⏭️ WhatsApp instance exists: {instance.friendly_name}")
    
    # 4. Restore Evolution Connections
    print("🔗 Restoring Evolution Connections...")
    for connection_data in backup_data['evolution_connections']:
        tenant = Tenant.objects.filter(id=connection_data['tenant_id']).first() if connection_data['tenant_id'] else None
        
        connection, created = EvolutionConnection.objects.get_or_create(
            id=connection_data['id'],
            defaults={
                'name': connection_data['name'],
                'base_url': connection_data['base_url'],
                'api_key': connection_data['api_key'],
                'webhook_url': connection_data['webhook_url'],
                'is_active': connection_data['is_active'],
                'status': connection_data['status'],
                'tenant': tenant,
            }
        )
        if created:
            print(f"   ✅ Created Evolution connection: {connection.name}")
        else:
            print(f"   ⏭️ Evolution connection exists: {connection.name}")
    
    print("=" * 60)
    print("✅ DATA RESTORATION COMPLETE!")
    print("=" * 60)
    
    return True

if __name__ == '__main__':
    restore_all_data()
