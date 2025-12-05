#!/usr/bin/env python
"""
Script para enviar notificações do sistema via WhatsApp
"""
import os
import sys
import django
from django.utils import timezone
from datetime import datetime

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import NotificationTemplate
from apps.notifications.services import send_whatsapp_notification, send_websocket_notification
from apps.authn.models import User
import logging

logger = logging.getLogger(__name__)

def send_celery_worker_down_notification(tenant_id=None):
    """Envia notificação quando workers do Celery param"""
    try:
        template = NotificationTemplate.objects.get(
            name='celery_worker_down',
            type='whatsapp',
            is_global=True,
            is_active=True
        )
        
        # Buscar usuários admin
        if tenant_id:
            users = User.objects.filter(tenant_id=tenant_id, role='admin')
        else:
            users = User.objects.filter(is_superuser=True)
        
        if not users.exists():
            users = User.objects.filter(is_staff=True)[:5]  # Fallback para staff
        
        context = {
            'timestamp': timezone.now().strftime('%d/%m/%Y %H:%M:%S'),
            'environment': os.getenv('RAILWAY_ENVIRONMENT', 'Production'),
            'tenant_name': users.first().tenant.name if users.exists() else 'Sistema'
        }
        
        notifications_sent = 0
        notifications_failed = 0
        
        for user in users:
            if not user.phone:
                logger.debug(f'⏭️ [SYSTEM NOTIFICATION] Pulando {user.email} - sem telefone')
                continue
            
            try:
                # Renderizar template com contexto
                message = template.content
                for key, value in context.items():
                    message = message.replace(f'{{{{{key}}}}}', str(value))
                
                # Enviar via WhatsApp
                success = send_whatsapp_notification(user, message)
                if success:
                    notifications_sent += 1
                    logger.info(f'✅ [SYSTEM NOTIFICATION] Notificação enviada para {user.email}')
                else:
                    notifications_failed += 1
                    logger.warning(f'⚠️ [SYSTEM NOTIFICATION] Falha ao enviar para {user.email}')
            except Exception as e:
                notifications_failed += 1
                logger.error(f'❌ [SYSTEM NOTIFICATION] Erro ao enviar para {user.email}: {e}', exc_info=True)
        
        logger.info(f'📊 [SYSTEM NOTIFICATION] Total: {notifications_sent} enviadas, {notifications_failed} falhas')
        return notifications_sent > 0
        
    except NotificationTemplate.DoesNotExist:
        print("❌ Template 'celery_worker_down' não encontrado")
        return False
    except Exception as e:
        print(f"❌ Erro ao enviar notificação: {e}")
        return False

def send_celery_worker_up_notification(tenant_id=None):
    """Envia notificação quando workers do Celery voltam"""
    try:
        template = NotificationTemplate.objects.get(
            name='celery_worker_up',
            type='whatsapp',
            is_global=True,
            is_active=True
        )
        
        # Buscar usuários admin
        if tenant_id:
            users = User.objects.filter(tenant_id=tenant_id, role='admin')
        else:
            users = User.objects.filter(is_superuser=True)
        
        if not users.exists():
            users = User.objects.filter(is_staff=True)[:5]
        
        context = {
            'timestamp': timezone.now().strftime('%d/%m/%Y %H:%M:%S'),
            'environment': os.getenv('RAILWAY_ENVIRONMENT', 'Production'),
            'tenant_name': users.first().tenant.name if users.exists() else 'Sistema'
        }
        
        notifications_sent = 0
        notifications_failed = 0
        
        for user in users:
            if not user.phone:
                logger.debug(f'⏭️ [SYSTEM NOTIFICATION] Pulando {user.email} - sem telefone')
                continue
            
            try:
                # Renderizar template com contexto
                message = template.content
                for key, value in context.items():
                    message = message.replace(f'{{{{{key}}}}}', str(value))
                
                # Enviar via WhatsApp
                success = send_whatsapp_notification(user, message)
                if success:
                    notifications_sent += 1
                    logger.info(f'✅ [SYSTEM NOTIFICATION] Notificação enviada para {user.email}')
                else:
                    notifications_failed += 1
                    logger.warning(f'⚠️ [SYSTEM NOTIFICATION] Falha ao enviar para {user.email}')
            except Exception as e:
                notifications_failed += 1
                logger.error(f'❌ [SYSTEM NOTIFICATION] Erro ao enviar para {user.email}: {e}', exc_info=True)
        
        logger.info(f'📊 [SYSTEM NOTIFICATION] Total: {notifications_sent} enviadas, {notifications_failed} falhas')
        return notifications_sent > 0
        
    except NotificationTemplate.DoesNotExist:
        print("❌ Template 'celery_worker_up' não encontrado")
        return False
    except Exception as e:
        print(f"❌ Erro ao enviar notificação: {e}")
        return False

def send_campaign_notification(campaign, event_type, tenant_id=None):
    """Envia notificação de eventos de campanha"""
    try:
        template_name = f'campaign_{event_type}'
        template = NotificationTemplate.objects.get(
            name=template_name,
            type='whatsapp',
            is_global=True,
            is_active=True
        )
        
        # Buscar usuários admin do tenant da campanha
        users = User.objects.filter(tenant=campaign.tenant, role='admin')
        if not users.exists():
            users = User.objects.filter(tenant=campaign.tenant)[:3]
        
        # Calcular estatísticas
        delivery_rate = campaign.success_rate if hasattr(campaign, 'success_rate') else 0
        read_rate = campaign.read_rate if hasattr(campaign, 'read_rate') else 0
        
        context = {
            'campaign_name': campaign.name,
            'total_contacts': campaign.total_contacts,
            'messages_sent': campaign.messages_sent,
            'messages_delivered': campaign.messages_delivered,
            'messages_read': campaign.messages_read,
            'messages_failed': campaign.messages_failed,
            'delivery_rate': f"{delivery_rate:.1f}%",
            'read_rate': f"{read_rate:.1f}%",
            'progress_percentage': campaign.progress_percentage if hasattr(campaign, 'progress_percentage') else 0,
            'rotation_mode': getattr(campaign, 'rotation_mode', 'Round Robin'),
            'tenant_name': campaign.tenant.name,
            'timestamp': timezone.now().strftime('%d/%m/%Y %H:%M:%S')
        }
        
        # Adicionar campos específicos por evento
        if event_type in ['started', 'paused', 'resumed', 'cancelled']:
            context[f'{event_type}_at'] = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
        elif event_type == 'completed':
            context['completed_at'] = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
            # Calcular duração (aproximada)
            if hasattr(campaign, 'started_at') and campaign.started_at:
                duration = timezone.now() - campaign.started_at
                hours = duration.total_seconds() // 3600
                minutes = (duration.total_seconds() % 3600) // 60
                context['duration'] = f"{int(hours)}h {int(minutes)}min"
            else:
                context['duration'] = "N/A"
        
        for user in users:
            if user.phone:
                send_notification_task.delay(str(template.id), user.id, context)
                print(f"📱 Notificação de campanha enviada para: {user.email}")
        
        return True
        
    except NotificationTemplate.DoesNotExist:
        print(f"❌ Template 'campaign_{event_type}' não encontrado")
        return False
    except Exception as e:
        print(f"❌ Erro ao enviar notificação de campanha: {e}")
        return False

def send_whatsapp_instance_notification(instance, event_type):
    """Envia notificação de eventos de instância WhatsApp"""
    try:
        template_name = f'whatsapp_instance_{event_type}'
        template = NotificationTemplate.objects.get(
            name=template_name,
            type='whatsapp',
            is_global=True,
            is_active=True
        )
        
        # Buscar usuários admin do tenant da instância
        users = User.objects.filter(tenant=instance.tenant, role='admin')
        if not users.exists():
            users = User.objects.filter(tenant=instance.tenant)[:3]
        
        context = {
            'instance_name': instance.friendly_name,
            'phone_number': instance.phone_number,
            'health_score': getattr(instance, 'health_score', 100),
            'tenant_name': instance.tenant.name if instance.tenant else 'Sistema',
            'timestamp': timezone.now().strftime('%d/%m/%Y %H:%M:%S')
        }
        
        # Adicionar campos específicos por evento
        if event_type == 'down':
            context['detected_at'] = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
            context['last_check'] = instance.last_check.strftime('%d/%m/%Y %H:%M:%S') if instance.last_check else 'N/A'
        elif event_type == 'up':
            context['connected_at'] = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
        
        for user in users:
            if user.phone:
                send_notification_task.delay(str(template.id), user.id, context)
                print(f"📱 Notificação de instância enviada para: {user.email}")
        
        return True
        
    except NotificationTemplate.DoesNotExist:
        print(f"❌ Template 'whatsapp_instance_{event_type}' não encontrado")
        return False
    except Exception as e:
        print(f"❌ Erro ao enviar notificação de instância: {e}")
        return False

def test_notification_system():
    """Testa o sistema de notificações"""
    print("🧪 Testando sistema de notificações...")
    
    # Verificar se templates existem
    templates = NotificationTemplate.objects.filter(type='whatsapp', is_global=True, is_active=True)
    print(f"📱 Templates WhatsApp disponíveis: {templates.count()}")
    
    for template in templates:
        print(f"   • {template.name}")
    
    # Verificar usuários com telefone
    users_with_phone = User.objects.exclude(phone__isnull=True).exclude(phone='')
    print(f"👥 Usuários com telefone: {users_with_phone.count()}")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1]
        
        if action == "worker_down":
            send_celery_worker_down_notification()
        elif action == "worker_up":
            send_celery_worker_up_notification()
        elif action == "test":
            test_notification_system()
        else:
            print("❌ Ação não reconhecida")
            print("Uso: python send_system_notifications.py [worker_down|worker_up|test]")
    else:
        test_notification_system()
