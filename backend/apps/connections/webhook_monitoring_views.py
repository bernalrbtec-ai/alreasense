"""
Views para monitoramento de webhooks em tempo real
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.decorators import user_passes_test

from .webhook_cache import WebhookCache

logger = logging.getLogger(__name__)


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser


class WebhookCacheStatsView(APIView):
    """
    View para obter estatísticas do cache de webhooks
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Retorna estatísticas do cache Redis"""
        try:
            # Verificar se é superuser
            if not request.user.is_superuser:
                return Response({
                    'error': 'Apenas administradores podem acessar esta funcionalidade'
                }, status=status.HTTP_403_FORBIDDEN)
            
            stats = WebhookCache.get_cache_stats()
            
            return Response({
                'status': 'success',
                'data': stats
            })
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter estatísticas do cache: {str(e)}")
            return Response({
                'error': 'Erro ao obter estatísticas do cache',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WebhookCacheEventsView(APIView):
    """
    View para listar eventos recentes do cache
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Retorna eventos recentes do cache"""
        try:
            # Verificar se é superuser
            if not request.user.is_superuser:
                return Response({
                    'error': 'Apenas administradores podem acessar esta funcionalidade'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Parâmetros opcionais
            hours = int(request.GET.get('hours', 24))
            limit = int(request.GET.get('limit', 100))
            
            events = WebhookCache.list_recent_events(hours=hours)
            
            # Limitar quantidade de eventos
            if limit > 0:
                events = events[:limit]
            
            return Response({
                'status': 'success',
                'data': {
                    'events': events,
                    'total': len(events),
                    'hours': hours,
                    'limit': limit
                }
            })
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar eventos do cache: {str(e)}")
            return Response({
                'error': 'Erro ao listar eventos do cache',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WebhookCacheReprocessView(APIView):
    """
    View para reprocessar eventos do cache
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Reprocessa eventos do cache"""
        try:
            # Verificar se é superuser
            if not request.user.is_superuser:
                return Response({
                    'error': 'Apenas administradores podem acessar esta funcionalidade'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Parâmetros opcionais
            event_types = request.data.get('event_types', None)
            
            stats = WebhookCache.reprocess_events(event_types=event_types)
            
            return Response({
                'status': 'success',
                'data': stats
            })
            
        except Exception as e:
            logger.error(f"❌ Erro ao reprocessar eventos: {str(e)}")
            return Response({
                'error': 'Erro ao reprocessar eventos',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WebhookCacheEventDetailView(APIView):
    """
    View para obter detalhes de um evento específico
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, event_id):
        """Retorna detalhes de um evento específico"""
        try:
            # Verificar se é superuser
            if not request.user.is_superuser:
                return Response({
                    'error': 'Apenas administradores podem acessar esta funcionalidade'
                }, status=status.HTTP_403_FORBIDDEN)
            
            event = WebhookCache.get_event(event_id)
            
            if not event:
                return Response({
                    'error': 'Evento não encontrado'
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'status': 'success',
                'data': event
            })
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter evento {event_id}: {str(e)}")
            return Response({
                'error': 'Erro ao obter evento',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
