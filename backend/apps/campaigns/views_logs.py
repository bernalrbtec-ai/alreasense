from rest_framework.decorators import api_view, permission_classes
from rest_framework.permission_classes import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count
from .models import CampaignLog, Campaign
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_logs(request):
    """Endpoint para buscar logs de campanhas com filtros"""
    try:
        user = request.user
        tenant = user.tenant
        
        # Parâmetros de filtro
        campaign_id = request.GET.get('campaign_id')
        log_type = request.GET.get('log_type')
        instance_name = request.GET.get('instance_name')
        contact_name = request.GET.get('contact_name')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        
        # Base query - apenas logs do tenant do usuário
        logs_query = CampaignLog.objects.filter(
            campaign__tenant=tenant
        ).select_related(
            'campaign', 
            'campaign_contact__contact',
            'user'
        ).order_by('-created_at')
        
        # Filtros
        if campaign_id:
            logs_query = logs_query.filter(campaign_id=campaign_id)
            
        if log_type:
            logs_query = logs_query.filter(log_type=log_type)
            
        if instance_name:
            logs_query = logs_query.filter(
                Q(instance_name__icontains=instance_name) |
                Q(message__icontains=instance_name)
            )
            
        if contact_name:
            logs_query = logs_query.filter(
                Q(campaign_contact__contact__name__icontains=contact_name) |
                Q(message__icontains=contact_name)
            )
            
        if date_from:
            try:
                from_date = timezone.datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                logs_query = logs_query.filter(created_at__gte=from_date)
            except ValueError:
                pass
                
        if date_to:
            try:
                to_date = timezone.datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                logs_query = logs_query.filter(created_at__lte=to_date)
            except ValueError:
                pass
        
        # Paginação
        total_count = logs_query.count()
        start = (page - 1) * page_size
        end = start + page_size
        logs = logs_query[start:end]
        
        # Serializar dados
        logs_data = []
        for log in logs:
            log_data = {
                'id': log.id,
                'created_at': log.created_at.isoformat(),
                'log_type': log.log_type,
                'log_type_display': log.get_log_type_display(),
                'message': log.message,
                'campaign_id': log.campaign.id if log.campaign else None,
                'campaign_name': log.campaign.name if log.campaign else None,
                'campaign_status': log.campaign.status if log.campaign else None,
                'contact_name': log.campaign_contact.contact.name if log.campaign_contact and log.campaign_contact.contact else None,
                'contact_phone': log.campaign_contact.contact.phone if log.campaign_contact and log.campaign_contact.contact else None,
                'instance_name': log.instance_name,
                'user_name': log.user.get_full_name() if log.user else 'Sistema',
                'extra_data': log.extra_data
            }
            logs_data.append(log_data)
        
        # Estatísticas
        stats = {
            'total_logs': total_count,
            'by_type': {},
            'by_campaign': {},
            'by_instance': {}
        }
        
        # Contar por tipo
        for log_type_choice in CampaignLog.LOG_TYPE_CHOICES:
            count = logs_query.filter(log_type=log_type_choice[0]).count()
            if count > 0:
                stats['by_type'][log_type_choice[0]] = {
                    'count': count,
                    'display': log_type_choice[1]
                }
        
        return Response({
            'success': True,
            'logs': logs_data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_next': end < total_count,
                'has_previous': page > 1
            },
            'stats': stats,
            'filters_applied': {
                'campaign_id': campaign_id,
                'log_type': log_type,
                'instance_name': instance_name,
                'contact_name': contact_name,
                'date_from': date_from,
                'date_to': date_to
            }
        })
        
    except Exception as e:
        logger.error(f"❌ [LOGS] Erro ao buscar logs: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_logs_stats(request):
    """Endpoint para estatísticas gerais dos logs"""
    try:
        user = request.user
        tenant = user.tenant
        
        # Últimos 24 horas
        last_24h = timezone.now() - timedelta(hours=24)
        
        # Contadores
        total_logs = CampaignLog.objects.filter(campaign__tenant=tenant).count()
        logs_24h = CampaignLog.objects.filter(
            campaign__tenant=tenant,
            created_at__gte=last_24h
        ).count()
        
        # Logs por tipo (últimas 24h)
        logs_by_type = {}
        for log_type_choice in CampaignLog.LOG_TYPE_CHOICES:
            count = CampaignLog.objects.filter(
                campaign__tenant=tenant,
                log_type=log_type_choice[0],
                created_at__gte=last_24h
            ).count()
            if count > 0:
                logs_by_type[log_type_choice[0]] = {
                    'count': count,
                    'display': log_type_choice[1]
                }
        
        # Campanhas mais ativas (últimas 24h)
        active_campaigns = CampaignLog.objects.filter(
            campaign__tenant=tenant,
            created_at__gte=last_24h
        ).values('campaign__name').annotate(
            log_count=Count('id')
        ).order_by('-log_count')[:5]
        
        return Response({
            'success': True,
            'stats': {
                'total_logs': total_logs,
                'logs_24h': logs_24h,
                'logs_by_type': logs_by_type,
                'active_campaigns': list(active_campaigns)
            }
        })
        
    except Exception as e:
        logger.error(f"❌ [LOGS-STATS] Erro ao buscar estatísticas: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
