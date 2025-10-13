#!/usr/bin/env python
"""
Script completo para backup e preservação de dados no Railway.
"""
import os
import django
import json
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import WhatsAppInstance
from apps.connections.models import EvolutionConnection
from apps.tenancy.models import Tenant
from apps.contacts.models import Contact
from apps.campaigns.models import Campaign
from django.contrib.auth import get_user_model

User = get_user_model()

def backup_all_data():
    """Faz backup completo de todos os dados críticos."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"/tmp/railway_backup_{timestamp}.json"
    
    print("🛡️ RAILWAY DATA BACKUP")
    print("=" * 60)
    
    backup_data = {
        'timestamp': timestamp,
        'tenants': [],
        'users': [],
        'whatsapp_instances': [],
        'evolution_connections': [],
        'contacts': [],
        'campaigns': [],
    }
    
    # 1. Backup Tenants
    print("📊 Backing up Tenants...")
    tenants = Tenant.objects.all()
    for tenant in tenants:
        backup_data['tenants'].append({
            'id': str(tenant.id),
            'name': tenant.name,
            'plan': tenant.current_plan.slug if tenant.current_plan else None,
            'status': tenant.status,
            'ui_access': tenant.ui_access,
        })
    print(f"   ✅ {tenants.count()} tenants backed up")
    
    # 2. Backup Users
    print("👤 Backing up Users...")
    users = User.objects.all()
    for user in users:
        backup_data['users'].append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'tenant_id': str(user.tenant.id) if user.tenant else None,
            'role': user.role,
        })
    print(f"   ✅ {users.count()} users backed up")
    
    # 3. Backup WhatsApp Instances
    print("📱 Backing up WhatsApp Instances...")
    instances = WhatsAppInstance.objects.all()
    for instance in instances:
        backup_data['whatsapp_instances'].append({
            'id': str(instance.id),
            'friendly_name': instance.friendly_name,
            'instance_name': instance.instance_name,
            'api_url': instance.api_url,
            'api_key': instance.api_key,
            'status': instance.status,
            'tenant_id': str(instance.tenant.id) if instance.tenant else None,
        })
    print(f"   ✅ {instances.count()} WhatsApp instances backed up")
    
    # 4. Backup Evolution Connections
    print("🔗 Backing up Evolution Connections...")
    connections = EvolutionConnection.objects.all()
    for connection in connections:
        backup_data['evolution_connections'].append({
            'id': str(connection.id),
            'name': connection.name,
            'base_url': connection.base_url,
            'api_key': connection.api_key,
            'webhook_url': connection.webhook_url,
            'is_active': connection.is_active,
            'status': connection.status,
            'tenant_id': str(connection.tenant.id) if connection.tenant else None,
        })
    print(f"   ✅ {connections.count()} Evolution connections backed up")
    
    # 5. Backup Contacts
    print("📇 Backing up Contacts...")
    contacts = Contact.objects.all()[:1000]  # Limit to avoid memory issues
    for contact in contacts:
        backup_data['contacts'].append({
            'id': str(contact.id),
            'name': contact.name,
            'phone': contact.phone,
            'email': contact.email,
            'state': contact.state,
            'city': contact.city,
            'tenant_id': str(contact.tenant.id) if contact.tenant else None,
        })
    print(f"   ✅ {contacts.count()} contacts backed up")
    
    # 6. Backup Campaigns
    print("📢 Backing up Campaigns...")
    campaigns = Campaign.objects.all()
    for campaign in campaigns:
        backup_data['campaigns'].append({
            'id': str(campaign.id),
            'name': campaign.name,
            'message': campaign.message,
            'status': campaign.status,
            'created_at': campaign.created_at.isoformat(),
            'tenant_id': str(campaign.tenant.id) if campaign.tenant else None,
        })
    print(f"   ✅ {campaigns.count()} campaigns backed up")
    
    # Save backup file
    with open(backup_file, 'w') as f:
        json.dump(backup_data, f, indent=2)
    
    print("=" * 60)
    print(f"✅ BACKUP COMPLETE: {backup_file}")
    print(f"📊 Total data backed up:")
    print(f"   - Tenants: {len(backup_data['tenants'])}")
    print(f"   - Users: {len(backup_data['users'])}")
    print(f"   - WhatsApp Instances: {len(backup_data['whatsapp_instances'])}")
    print(f"   - Evolution Connections: {len(backup_data['evolution_connections'])}")
    print(f"   - Contacts: {len(backup_data['contacts'])}")
    print(f"   - Campaigns: {len(backup_data['campaigns'])}")
    print("=" * 60)
    
    return backup_file

if __name__ == '__main__':
    backup_all_data()
