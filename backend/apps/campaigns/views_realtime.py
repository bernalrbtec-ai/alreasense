"""
Views para status em tempo real das campanhas
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from .models import Campaign


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_realtime_status(request, campaign_id):
    """Retorna status em tempo real da campanha com contador regressivo"""
    try:
        campaign = Campaign.objects.get(
            id=campaign_id,
            tenant=request.user.tenant
        )
        
        # Calcular tempo restante para próxima mensagem
        time_remaining = None
        if campaign.next_message_scheduled_at and campaign.status == 'running':
            now = timezone.now()
            if campaign.next_message_scheduled_at > now:
                delta = campaign.next_message_scheduled_at - now
                time_remaining = int(delta.total_seconds())
            else:
                time_remaining = 0
        
        # Calcular progresso
        total_contacts = campaign.total_contacts or 0
        progress_percentage = 0
        if total_contacts > 0:
            progress_percentage = (campaign.messages_sent / total_contacts) * 100
        
        return Response({
            'campaign_id': str(campaign.id),
            'name': campaign.name,
            'status': campaign.status,
            'progress': {
                'messages_sent': campaign.messages_sent,
                'messages_delivered': campaign.messages_delivered,
                'messages_read': campaign.messages_read,
                'messages_failed': campaign.messages_failed,
                'total_contacts': total_contacts,
                'percentage': round(progress_percentage, 1)
            },
            'next_message': {
                'contact_name': campaign.next_contact_name,
                'contact_phone': campaign.next_contact_phone,
                'scheduled_at': campaign.next_message_scheduled_at.isoformat() if campaign.next_message_scheduled_at else None,
                'time_remaining_seconds': time_remaining
            },
            'timing': {
                'interval_min': campaign.interval_min,
                'interval_max': campaign.interval_max,
                'rotation_mode': campaign.rotation_mode
            },
            'last_activity': {
                'started_at': campaign.started_at.isoformat() if campaign.started_at else None,
                'updated_at': campaign.updated_at.isoformat()
            }
        })
        
    except Campaign.DoesNotExist:
        return Response(
            {'error': 'Campanha não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Erro ao buscar status: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_realtime_progress(request, campaign_id):
    """Retorna apenas o progresso em tempo real (para polling frequente)"""
    try:
        campaign = Campaign.objects.get(
            id=campaign_id,
            tenant=request.user.tenant
        )
        
        # Calcular tempo restante
        time_remaining = None
        if campaign.next_message_scheduled_at and campaign.status == 'running':
            now = timezone.now()
            if campaign.next_message_scheduled_at > now:
                delta = campaign.next_message_scheduled_at - now
                time_remaining = int(delta.total_seconds())
            else:
                time_remaining = 0
        
        return Response({
            'status': campaign.status,
            'messages_sent': campaign.messages_sent,
            'time_remaining_seconds': time_remaining,
            'next_contact_name': campaign.next_contact_name,
            'updated_at': campaign.updated_at.isoformat()
        })
        
    except Campaign.DoesNotExist:
        return Response(
            {'error': 'Campanha não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Erro ao buscar progresso: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
