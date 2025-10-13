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
        else:
            print(f"   ⏭️ Exists: {instance.friendly_name}")
    
    print("=" * 50)
    print("✅ WhatsApp instances restored!")
    
    return True

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'restore':
        restore_whatsapp_instances()
    else:
        preserve_whatsapp_instances()
