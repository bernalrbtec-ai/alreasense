#!/usr/bin/env python
"""
Script específico para preservar configurações de WhatsApp Instances.
"""
import os
import django
import json
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import WhatsAppInstance

def preserve_whatsapp_instances():
    """Preserva apenas as configurações de WhatsApp Instances."""
    print("📱 PRESERVING WHATSAPP INSTANCES")
    print("=" * 50)
    print("🛡️ Railway Deploy Protection Active")
    
    # Backup file
    backup_file = "/tmp/whatsapp_instances_backup.json"
    
    # Get all WhatsApp instances
    instances = WhatsAppInstance.objects.all()
    print(f"📊 Found {instances.count()} WhatsApp instances")
    
    backup_data = {
        'timestamp': datetime.now().isoformat(),
        'instances': []
    }
    
    for instance in instances:
        instance_data = {
            'id': str(instance.id),
            'friendly_name': instance.friendly_name,
            'instance_name': instance.instance_name,
            'api_url': instance.api_url,
            'api_key': instance.api_key,
            'status': instance.status,
            'tenant_id': str(instance.tenant.id) if instance.tenant else None,
            'created_at': instance.created_at.isoformat(),
            'updated_at': instance.updated_at.isoformat(),
        }
        backup_data['instances'].append(instance_data)
        print(f"   ✅ Backed up: {instance.friendly_name}")
        print(f"      API URL: {instance.api_url}")
        print(f"      Instance Name: {instance.instance_name}")
    
    # Save backup
    with open(backup_file, 'w') as f:
        json.dump(backup_data, f, indent=2)
    
    print("=" * 50)
    print(f"✅ WhatsApp instances backed up to: {backup_file}")
    print(f"📊 Total instances: {len(backup_data['instances'])}")
    
    return backup_file

def restore_whatsapp_instances():
    """Restaura as configurações de WhatsApp Instances."""
    print("🔄 RESTORING WHATSAPP INSTANCES")
    print("=" * 50)
    
    backup_file = "/tmp/whatsapp_instances_backup.json"
    
    if not os.path.exists(backup_file):
        print("❌ No backup file found!")
        return False
    
    # Load backup
    with open(backup_file, 'r') as f:
        backup_data = json.load(f)
    
    print(f"📅 Backup timestamp: {backup_data['timestamp']}")
    
    # Restore instances
    from apps.tenancy.models import Tenant
    
    for instance_data in backup_data['instances']:
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
            print(f"   ✅ Restored: {instance.friendly_name}")
            print(f"      API URL: {instance.api_url}")
            print(f"      Instance Name: {instance.instance_name}")
        else:
            print(f"   ⏭️ Exists: {instance.friendly_name}")
            print(f"      API URL: {instance.api_url}")
            print(f"      Instance Name: {instance.instance_name}")
    
    print("=" * 50)
    print("✅ WhatsApp instances restored!")
    
    return True

def check_whatsapp_instances():
    """Verifica quantas WhatsApp Instances existem."""
    print("🔍 CHECKING WHATSAPP INSTANCES")
    print("=" * 50)
    
    instances = WhatsAppInstance.objects.all()
    print(f"📊 Found {instances.count()} WhatsApp instances")
    
    for instance in instances:
        print(f"   📱 {instance.friendly_name}")
        print(f"      API URL: {instance.api_url}")
        print(f"      Status: {instance.status}")
    
    print("=" * 50)
    return instances.count()

def verify_whatsapp_instances():
    """Verifica se as WhatsApp Instances ainda existem após migrations."""
    print("✅ VERIFYING WHATSAPP INSTANCES")
    print("=" * 50)
    
    instances = WhatsAppInstance.objects.all()
    print(f"📊 Found {instances.count()} WhatsApp instances after migrations")
    
    if instances.count() == 0:
        print("❌ WARNING: No WhatsApp instances found after migrations!")
        print("   This means migrations are deleting the data!")
    else:
        print("✅ WhatsApp instances preserved successfully!")
        for instance in instances:
            print(f"   📱 {instance.friendly_name}")
            print(f"      API URL: {instance.api_url}")
    
    print("=" * 50)
    return instances.count()

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == 'restore':
            restore_whatsapp_instances()
        elif sys.argv[1] == 'check':
            check_whatsapp_instances()
        elif sys.argv[1] == 'verify':
            verify_whatsapp_instances()
        else:
            preserve_whatsapp_instances()
    else:
        preserve_whatsapp_instances()
