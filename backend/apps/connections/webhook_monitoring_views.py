"""
Views para monitoramento de webhooks em tempo real
"""

import logging
import json
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
    View para listar eventos recentes do cache com filtros e paginação
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Retorna eventos recentes do cache com filtros e paginação"""
        try:
            # Verificar se é superuser
            if not request.user.is_superuser:
                return Response({
                    'error': 'Apenas administradores podem acessar esta funcionalidade'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Parâmetros de filtro
            hours = int(request.GET.get('hours', 24))
            event_type = request.GET.get('event_type', '')  # Filtro por tipo de evento
            start_date = request.GET.get('start_date', '')  # Filtro por data inicial
            end_date = request.GET.get('end_date', '')      # Filtro por data final
            instance = request.GET.get('instance', '')      # Filtro por instância
            
            # Parâmetros de paginação
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 50))
            
            # Obter todos os eventos
            events = WebhookCache.list_recent_events(hours=hours)
            
            # Aplicar filtros
            filtered_events = []
            for event in events:
                # Função flexível para extrair dados do evento
                def extract_event_data(event_obj):
                    """Extrai dados do evento de forma flexível"""
                    try:
                        # Se é lista, pegar primeiro item
                        if isinstance(event_obj, list):
                            event_obj = event_obj[0] if event_obj else {}
                        
                        # Se é string, tentar fazer parse JSON
                        if isinstance(event_obj, str):
                            try:
                                event_obj = json.loads(event_obj)
                            except json.JSONDecodeError:
                                return {}
                        
                        # Se tem campo 'data', usar ele
                        if isinstance(event_obj, dict) and 'data' in event_obj:
                            data_field = event_obj['data']
                            
                            # Se data é string, tentar parse
                            if isinstance(data_field, str):
                                try:
                                    data_field = json.loads(data_field)
                                except json.JSONDecodeError:
                                    data_field = {}
                            
                            # Mesclar dados do evento com dados internos
                            result = event_obj.copy()
                            if isinstance(data_field, dict):
                                result.update(data_field)
                            return result
                        
                        # Se não tem campo 'data', usar o objeto diretamente
                        return event_obj if isinstance(event_obj, dict) else {}
                        
                    except Exception as e:
                        logger.warning(f"Erro ao extrair dados do evento: {str(e)}")
                        return {}
                
                # Extrair dados do evento
                event_data = extract_event_data(event)
                
                # Filtro por tipo de evento
                if event_type and event_type.lower() not in event_data.get('event', '').lower():
                    continue
                
                # Filtro por instância
                if instance and instance.lower() not in event_data.get('instance', '').lower():
                    continue
                
                # Filtro por data (se fornecido)
                if start_date or end_date:
                    event_time = event_data.get('date_time', '')
                    if event_time:
                        try:
                            from datetime import datetime
                            event_datetime = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                            
                            if start_date:
                                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                                if event_datetime < start_datetime:
                                    continue
                            
                            if end_date:
                                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                if event_datetime > end_datetime:
                                    continue
                        except ValueError:
                            # Se não conseguir parsear a data, inclui o evento
                            pass
                
                filtered_events.append(event_data)
            
            # Ordenar por data (mais recentes primeiro)
            def get_sort_key(event_obj):
                """Extrai chave de ordenação de forma flexível"""
                # Tentar diferentes campos de data
                date_fields = ['date_time', '_cached_at', 'created_at', 'timestamp']
                for field in date_fields:
                    date_value = event_obj.get(field, '')
                    if date_value:
                        return date_value
                
                # Se não encontrar data, usar string vazia
                return ''
            
            filtered_events.sort(key=get_sort_key, reverse=True)
            
            # Aplicar paginação
            total_events = len(filtered_events)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_events = filtered_events[start_index:end_index]
            
            # Calcular informações de paginação
            total_pages = (total_events + page_size - 1) // page_size
            has_next = page < total_pages
            has_previous = page > 1
            
            return Response({
                'status': 'success',
                'data': {
                    'events': paginated_events,
                    'pagination': {
                        'current_page': page,
                        'page_size': page_size,
                        'total_events': total_events,
                        'total_pages': total_pages,
                        'has_next': has_next,
                        'has_previous': has_previous
                    },
                    'filters': {
                        'hours': hours,
                        'event_type': event_type,
                        'start_date': start_date,
                        'end_date': end_date,
                        'instance': instance
                    }
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
