from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import models
import requests
import logging

from .models import NotificationTemplate, WhatsAppInstance, NotificationLog

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_notification_task(self, template_id, recipient_id, context=None):
    """
    Send a notification based on template.
    
    Args:
        template_id: UUID of the notification template
        recipient_id: ID of the recipient user
        context: Dict with variables to render in template
    """
    context = context or {}
    
    try:
        template = NotificationTemplate.objects.get(id=template_id)
        recipient = User.objects.get(id=recipient_id)
        
        # Render template with context
        rendered = template.render(context)
        
        # Create notification log
        log = NotificationLog.objects.create(
            tenant=recipient.tenant,
            template=template,
            recipient=recipient,
            recipient_email=recipient.email,
            recipient_phone=recipient.phone or '',
            type=template.type,
            subject=rendered['subject'],
            content=rendered['content'],
            status='pending',
            metadata={'context': context}
        )
        
        # Send based on type
        if template.type == 'email':
            send_email_notification.delay(log.id)
        elif template.type == 'whatsapp':
            send_whatsapp_notification.delay(log.id)
        
        return {
            'success': True,
            'log_id': str(log.id)
        }
    
    except Exception as e:
        logger.error(f"Error in send_notification_task: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_email_notification(self, log_id):
    """
    Send email notification.
    
    Args:
        log_id: UUID of the notification log
    """
    try:
        log = NotificationLog.objects.get(id=log_id)
        
        if not log.recipient_email:
            log.status = 'failed'
            log.error_message = 'Email do destinatário não informado'
            log.save()
            return {'success': False, 'error': 'No recipient email'}
        
        # Send email
        send_mail(
            subject=log.subject,
            message=log.content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[log.recipient_email],
            fail_silently=False,
        )
        
        # Update log
        log.status = 'sent'
        log.sent_at = timezone.now()
        log.save()
        
        logger.info(f"Email sent to {log.recipient_email}: {log.subject}")
        
        return {
            'success': True,
            'log_id': str(log.id)
        }
    
    except NotificationLog.DoesNotExist:
        logger.error(f"NotificationLog {log_id} not found")
        return {'success': False, 'error': 'Log not found'}
    
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        
        try:
            log = NotificationLog.objects.get(id=log_id)
            log.status = 'failed'
            log.error_message = str(e)
            log.save()
        except:
            pass
        
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_whatsapp_notification(self, log_id):
    """
    Send WhatsApp notification via Evolution API.
    
    Args:
        log_id: UUID of the notification log
    """
    try:
        log = NotificationLog.objects.get(id=log_id)
        
        if not log.recipient_phone:
            log.status = 'failed'
            log.error_message = 'Telefone do destinatário não informado'
            log.save()
            return {'success': False, 'error': 'No recipient phone'}
        
        # Get WhatsApp instance (default or first active)
        instance = WhatsAppInstance.objects.filter(
            tenant=log.tenant,
            is_active=True,
            status='active'
        ).filter(
            models.Q(is_default=True) | models.Q(is_default=False)
        ).order_by('-is_default').first()
        
        if not instance:
            log.status = 'failed'
            log.error_message = 'Nenhuma instância WhatsApp ativa encontrada'
            log.save()
            return {'success': False, 'error': 'No active WhatsApp instance'}
        
        log.whatsapp_instance = instance
        log.save()
        
        # Format phone number (remove non-digits)
        phone = ''.join(filter(str.isdigit, log.recipient_phone))
        
        # Send message via Evolution API
        response = requests.post(
            f"{instance.api_url}/message/sendText/{instance.instance_name}",
            headers={'apikey': instance.api_key},
            json={
                'number': phone,
                'text': log.content
            },
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            
            # Update log
            log.status = 'sent'
            log.sent_at = timezone.now()
            log.external_id = data.get('key', {}).get('id', '')
            log.save()
            
            logger.info(f"WhatsApp sent to {phone}: {log.subject}")
            
            return {
                'success': True,
                'log_id': str(log.id),
                'message_id': log.external_id
            }
        else:
            raise Exception(f"Evolution API error: {response.text}")
    
    except NotificationLog.DoesNotExist:
        logger.error(f"NotificationLog {log_id} not found")
        return {'success': False, 'error': 'Log not found'}
    
    except Exception as e:
        logger.error(f"Error sending WhatsApp: {str(e)}")
        
        try:
            log = NotificationLog.objects.get(id=log_id)
            log.status = 'failed'
            log.error_message = str(e)
            log.save()
        except:
            pass
        
        raise self.retry(exc=e, countdown=60)


@shared_task
def check_whatsapp_instances_status():
    """
    Periodic task to check all WhatsApp instances status.
    """
    instances = WhatsAppInstance.objects.filter(is_active=True)
    
    for instance in instances:
        try:
            instance.check_status()
            logger.info(f"Checked WhatsApp instance {instance.name}: {instance.status}")
        except Exception as e:
            logger.error(f"Error checking instance {instance.name}: {str(e)}")
    
    return {
        'success': True,
        'checked': instances.count()
    }


@shared_task
def send_welcome_notification(user_id):
    """
    Send welcome notification to new user.
    
    Args:
        user_id: ID of the new user
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Find welcome template for tenant or global
        template = NotificationTemplate.objects.filter(
            category='welcome',
            is_active=True
        ).filter(
            models.Q(tenant=user.tenant) | models.Q(is_global=True)
        ).first()
        
        if not template:
            logger.warning(f"No welcome template found for user {user.email}")
            return {'success': False, 'error': 'No template found'}
        
        # Context for template
        context = {
            'user_name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'user_email': user.email,
            'tenant_name': user.tenant.name,
            'plan_name': user.tenant.plan,
        }
        
        # Send notification
        send_notification_task.delay(str(template.id), user.id, context)
        
        return {'success': True}
    
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'success': False, 'error': 'User not found'}
    
    except Exception as e:
        logger.error(f"Error sending welcome notification: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def send_plan_change_notification(tenant_id, old_plan, new_plan):
    """
    Send plan change notification to tenant admin.
    
    Args:
        tenant_id: UUID of the tenant
        old_plan: Name of the old plan
        new_plan: Name of the new plan
    """
    try:
        from apps.tenancy.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)
        
        # Find plan change template
        template = NotificationTemplate.objects.filter(
            category='plan_change',
            is_active=True
        ).filter(
            models.Q(tenant=tenant) | models.Q(is_global=True)
        ).first()
        
        if not template:
            logger.warning(f"No plan change template found for tenant {tenant.name}")
            return {'success': False, 'error': 'No template found'}
        
        # Get tenant admin users
        admin_users = User.objects.filter(tenant=tenant, role='admin')
        
        # Context for template
        context = {
            'tenant_name': tenant.name,
            'old_plan': old_plan,
            'new_plan': new_plan,
        }
        
        # Send to all admins
        for user in admin_users:
            context['user_name'] = f"{user.first_name} {user.last_name}".strip() or user.username
            send_notification_task.delay(str(template.id), user.id, context)
        
        return {'success': True, 'sent_to': admin_users.count()}
    
    except Exception as e:
        logger.error(f"Error sending plan change notification: {str(e)}")
        return {'success': False, 'error': str(e)}

