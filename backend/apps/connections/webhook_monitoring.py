"""
Webhook Monitoring - Endpoints para monitorar e gerenciar cache de webhooks
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from .webhook_cache import WebhookCache
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def webhook_cache_stats(request):
    """
    Retorna estatísticas do cache de webhooks.
    Apenas para administradores.
    """
    try:
        stats = WebhookCache.get_cache_stats()
        return Response({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas do cache: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def webhook_recent_events(request):
    """
    Lista eventos webhook recentes do cache.
    Apenas para administradores.
    """
    try:
        hours = int(request.GET.get('hours', 24))
        events = WebhookCache.list_recent_events(hours=hours)
        
        return Response({
            'success': True,
            'data': {
                'events': events,
                'count': len(events),
                'hours': hours
            }
        })
    except Exception as e:
        logger.error(f"Erro ao listar eventos recentes: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def webhook_reprocess_events(request):
    """
    Reprocessa eventos do cache.
    Apenas para administradores.
    """
    try:
        event_types = request.data.get('event_types', None)
        stats = WebhookCache.reprocess_events(event_types=event_types)
        
        return Response({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"Erro ao reprocessar eventos: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def webhook_event_details(request, event_id):
    """
    Retorna detalhes de um evento específico do cache.
    Apenas para administradores.
    """
    try:
        event_data = WebhookCache.get_event(event_id)
        
        if not event_data:
            return Response({
                'success': False,
                'error': 'Evento não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'success': True,
            'data': event_data
        })
    except Exception as e:
        logger.error(f"Erro ao obter detalhes do evento: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
