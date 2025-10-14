"""
Views customizadas para o Django Admin - Monitoramento do RabbitMQ
"""

from django.contrib import admin
from django.shortcuts import render
from django.urls import path, reverse
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import user_passes_test
from django.utils.html import format_html
from django.db import models
from django.contrib import messages
from django.utils import timezone
import json
import logging

from apps.campaigns.rabbitmq_consumer import get_rabbitmq_consumer
from apps.common.health import get_system_health

logger = logging.getLogger(__name__)


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser


class RabbitMQMonitoringAdminMixin:
    """Mixin para adicionar funcionalidade de monitoramento do RabbitMQ ao admin"""
    
    def get_urls(self):
        """Adiciona URLs customizadas ao admin"""
        urls = super().get_urls()
        custom_urls = [
            path(
                'rabbitmq-monitoring/',
                self.admin_site.admin_view(self.rabbitmq_monitoring_view),
                name='campaigns_campaign_rabbitmq_monitoring',
            ),
            path(
                'rabbitmq-monitoring/api/',
                self.admin_site.admin_view(self.rabbitmq_monitoring_api),
                name='campaigns_campaign_rabbitmq_monitoring_api',
            ),
            path(
                'rabbitmq-monitoring/queue-stats/',
                self.admin_site.admin_view(self.queue_stats_api),
                name='campaigns_campaign_queue_stats_api',
            ),
            path(
                'rabbitmq-monitoring/control/',
                self.admin_site.admin_view(self.rabbitmq_control_api),
                name='campaigns_campaign_rabbitmq_control_api',
            ),
        ]
        return custom_urls + urls
    
    @method_decorator(user_passes_test(is_superuser))
    def rabbitmq_monitoring_view(self, request):
        """View para renderizar a página de monitoramento do RabbitMQ"""
        
        # Obter dados do sistema
        try:
            system_health = get_system_health()
            rabbitmq_status = system_health.get('rabbitmq_status', {})
        except Exception as e:
            logger.error(f"Erro ao obter status do sistema: {e}")
            rabbitmq_status = {'status': 'error', 'error': str(e)}
        
        # Obter consumer
        try:
            consumer = get_rabbitmq_consumer()
            if consumer:
                active_campaigns = consumer.get_active_campaigns()
                consumer_status = 'running'
            else:
                active_campaigns = []
                consumer_status = 'not_configured'
        except Exception as e:
            logger.error(f"Erro ao obter consumer: {e}")
            active_campaigns = []
            consumer_status = 'error'
        
        # Obter estatísticas das campanhas
        from .models import Campaign, CampaignContact
        try:
            total_campaigns = Campaign.objects.count()
            running_campaigns = Campaign.objects.filter(status='running').count()
            paused_campaigns = Campaign.objects.filter(status='paused').count()
            
            # Contatos pendentes
            pending_contacts = CampaignContact.objects.filter(
                status__in=['pending', 'sending']
            ).count()
            
            # Estatísticas de mensagens
            from django.db.models import Sum
            message_stats = Campaign.objects.aggregate(
                total_sent=Sum('messages_sent'),
                total_delivered=Sum('messages_delivered'),
                total_failed=Sum('messages_failed')
            )
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            total_campaigns = 0
            running_campaigns = 0
            paused_campaigns = 0
            pending_contacts = 0
            message_stats = {'total_sent': 0, 'total_delivered': 0, 'total_failed': 0}
        
        context = {
            'title': 'Monitoramento do RabbitMQ',
            'rabbitmq_status': rabbitmq_status,
            'consumer_status': consumer_status,
            'active_campaigns': active_campaigns,
            'active_campaigns_count': len(active_campaigns),
            'total_campaigns': total_campaigns,
            'running_campaigns': running_campaigns,
            'paused_campaigns': paused_campaigns,
            'pending_contacts': pending_contacts,
            'message_stats': message_stats,
            'has_permission': True,
            'opts': self.model._meta,
            'current_time': timezone.now(),
        }
        
        return render(request, 'admin/campaigns/campaign/rabbitmq_monitoring.html', context)
    
    @method_decorator(user_passes_test(is_superuser))
    @require_http_methods(["GET"])
    def rabbitmq_monitoring_api(self, request):
        """API para obter dados do monitoramento do RabbitMQ"""
        
        try:
            # Obter status do sistema
            system_health = get_system_health()
            rabbitmq_status = system_health.get('rabbitmq_status', {})
            
            # Obter consumer
            consumer = get_rabbitmq_consumer()
            if consumer:
                active_campaigns = consumer.get_active_campaigns()
                consumer_running = True
                
                # Obter detalhes das campanhas ativas
                campaign_details = []
                for campaign_id in active_campaigns:
                    try:
                        campaign_status = consumer.get_campaign_status(campaign_id)
                        campaign_details.append({
                            'campaign_id': campaign_id,
                            'status': campaign_status.get('status', 'unknown'),
                            'is_running': campaign_status.get('is_running', False),
                            'messages_processed': campaign_status.get('messages_processed', 0),
                            'last_activity': campaign_status.get('last_activity', None),
                        })
                    except Exception as e:
                        logger.warning(f"Erro ao obter status da campanha {campaign_id}: {e}")
                        campaign_details.append({
                            'campaign_id': campaign_id,
                            'status': 'error',
                            'error': str(e)
                        })
            else:
                active_campaigns = []
                consumer_running = False
                campaign_details = []
            
            # Estatísticas do banco
            from .models import Campaign, CampaignContact
            from django.db.models import Sum, Count
            
            db_stats = {
                'total_campaigns': Campaign.objects.count(),
                'running_campaigns': Campaign.objects.filter(status='running').count(),
                'paused_campaigns': Campaign.objects.filter(status='paused').count(),
                'pending_contacts': CampaignContact.objects.filter(
                    status__in=['pending', 'sending']
                ).count(),
                'message_stats': Campaign.objects.aggregate(
                    total_sent=Sum('messages_sent') or 0,
                    total_delivered=Sum('messages_delivered') or 0,
                    total_failed=Sum('messages_failed') or 0,
                )
            }
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'rabbitmq_status': rabbitmq_status,
                    'consumer_running': consumer_running,
                    'active_campaigns': active_campaigns,
                    'active_campaigns_count': len(active_campaigns),
                    'campaign_details': campaign_details,
                    'db_stats': db_stats,
                    'timestamp': timezone.now().isoformat(),
                }
            })
            
        except Exception as e:
            logger.error(f"Erro na API de monitoramento RabbitMQ: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    @method_decorator(user_passes_test(is_superuser))
    @require_http_methods(["GET"])
    def queue_stats_api(self, request):
        """API para obter estatísticas das filas"""
        
        try:
            consumer = get_rabbitmq_consumer()
            if not consumer:
                return JsonResponse({
                    'status': 'error',
                    'message': 'RabbitMQ Consumer não está configurado'
                }, status=503)
            
            # Tentar obter estatísticas das filas (se disponível)
            queue_stats = {
                'total_queues': 0,
                'active_queues': 0,
                'messages_in_queue': 0,
                'queues': []
            }
            
            # Para cada campanha ativa, tentar obter estatísticas da fila
            active_campaigns = consumer.get_active_campaigns()
            for campaign_id in active_campaigns:
                try:
                    campaign_status = consumer.get_campaign_status(campaign_id)
                    queue_stats['queues'].append({
                        'campaign_id': campaign_id,
                        'status': campaign_status.get('status', 'unknown'),
                        'is_running': campaign_status.get('is_running', False),
                        'messages_processed': campaign_status.get('messages_processed', 0),
                    })
                    if campaign_status.get('is_running', False):
                        queue_stats['active_queues'] += 1
                    queue_stats['total_queues'] += 1
                except Exception as e:
                    logger.warning(f"Erro ao obter estatísticas da fila {campaign_id}: {e}")
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'queue_stats': queue_stats,
                    'timestamp': timezone.now().isoformat(),
                }
            })
            
        except Exception as e:
            logger.error(f"Erro na API de estatísticas das filas: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    @method_decorator(user_passes_test(is_superuser))
    @require_http_methods(["POST"])
    def rabbitmq_control_api(self, request):
        """API para controlar o RabbitMQ Consumer (start/stop/restart)"""
        
        try:
            action = request.POST.get('action', '').lower()
            consumer = get_rabbitmq_consumer()
            
            if not consumer:
                return JsonResponse({
                    'status': 'error',
                    'message': 'RabbitMQ Consumer não está configurado'
                }, status=503)
            
            if action == 'start':
                success, message = consumer.force_start()
            elif action == 'stop':
                success, message = consumer.force_stop()
            elif action == 'restart':
                success, message = consumer.force_restart()
            elif action == 'status':
                detailed_status = consumer.get_detailed_status()
                return JsonResponse({
                    'status': 'success',
                    'data': detailed_status,
                    'timestamp': timezone.now().isoformat(),
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Ação inválida. Use: start, stop, restart ou status'
                }, status=400)
            
            if success:
                # Obter status atualizado após a ação
                detailed_status = consumer.get_detailed_status()
                return JsonResponse({
                    'status': 'success',
                    'message': message,
                    'data': detailed_status,
                    'timestamp': timezone.now().isoformat(),
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': message
                }, status=500)
                
        except Exception as e:
            logger.error(f"Erro na API de controle RabbitMQ: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
