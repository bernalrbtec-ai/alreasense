"""
Views customizadas para o Django Admin - Monitoramento de Webhooks
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
import json
import logging

from .webhook_cache import WebhookCache

logger = logging.getLogger(__name__)


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser


class WebhookMonitoringAdminMixin:
    """Mixin para adicionar funcionalidade de monitoramento de webhooks ao admin"""
    
    def get_urls(self):
        """Adiciona URLs customizadas ao admin"""
        urls = super().get_urls()
        custom_urls = [
            path(
                'webhook-monitoring/',
                self.admin_site.admin_view(self.webhook_monitoring_view),
                name='connections_evolutionconnection_webhook_monitoring',
            ),
            path(
                'webhook-monitoring/api/',
                self.admin_site.admin_view(self.webhook_monitoring_api),
                name='connections_evolutionconnection_webhook_monitoring_api',
            ),
            path(
                'webhook-monitoring/distribution/',
                self.admin_site.admin_view(self.webhook_events_distribution_api),
                name='connections_evolutionconnection_webhook_distribution_api',
            ),
        ]
        return custom_urls + urls
    
    @method_decorator(user_passes_test(is_superuser))
    @require_http_methods(["GET"])
    def webhook_events_distribution_api(self, request):
        """API para obter distribuição de eventos por tipo"""
        
        try:
            hours = int(request.GET.get('hours', 24))
            
            # Obter eventos recentes
            events = WebhookCache.list_recent_events(hours=hours)
            
            # Calcular distribuição por tipo de evento
            events_by_type = {}
            for event in events:
                try:
                    event_type = self._extract_event_type(event)
                    if event_type:
                        events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
                except Exception as e:
                    logger.warning(f"Erro ao extrair tipo do evento: {e}")
                    continue
            
            # Ordenar por quantidade (mais frequentes primeiro)
            events_by_type = dict(sorted(events_by_type.items(), key=lambda x: x[1], reverse=True))
            
            # Definir ícones para cada tipo de evento
            event_icons = {
                'messages.upsert': '📥',
                'messages.update': '📤',
                'messages.delete': '🗑️',
                'messages.edited': '✏️',
                'chats.update': '💬',
                'chats.upsert': '💬',
                'chats.delete': '🗑️',
                'chats.set': '⚙️',
                'connection.update': '🔗',
                'contacts.update': '👥',
                'contacts.upsert': '👤',
                'presence.update': '👁️',
                'qrcode.updated': '📱',
                'send.message': '📨',
                'group-participants.update': '👥',
                'labels.edit': '🏷️',
                'messages.set': '📝',
            }
            
            # Formatar resposta
            distribution_data = []
            for event_type, count in events_by_type.items():
                distribution_data.append({
                    'event_type': event_type,
                    'count': count,
                    'icon': event_icons.get(event_type, '📄'),
                    'percentage': round((count / len(events)) * 100, 2) if events else 0
                })
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'distribution': distribution_data,
                    'total_events': len(events),
                    'hours': hours
                }
            })
            
        except Exception as e:
            logger.error(f"Erro na API de distribuição de eventos: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    @method_decorator(user_passes_test(is_superuser))
    def webhook_monitoring_view(self, request):
        """View para renderizar a página de monitoramento de webhooks"""
        
        # Obter estatísticas do cache
        try:
            cache_stats = WebhookCache.get_cache_stats()
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas do cache: {e}")
            cache_stats = {
                'total_events': 0,
                'events_by_type': {},
                'recent_events': []
            }
        
        # Obter eventos recentes
        try:
            recent_events = WebhookCache.list_recent_events(hours=24)
        except Exception as e:
            logger.error(f"Erro ao listar eventos recentes: {e}")
            recent_events = []
        
        # Calcular distribuição por tipo de evento
        events_by_type = {}
        for event in recent_events:
            try:
                # Extrair tipo do evento de forma flexível
                event_type = self._extract_event_type(event)
                if event_type:
                    events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
            except Exception as e:
                logger.warning(f"Erro ao extrair tipo do evento: {e}")
                continue
        
        # Ordenar por quantidade (mais frequentes primeiro)
        events_by_type = dict(sorted(events_by_type.items(), key=lambda x: x[1], reverse=True))
        
        # Definir ícones para cada tipo de evento
        event_icons = {
            'messages.upsert': '📥',
            'messages.update': '📤',
            'messages.delete': '🗑️',
            'messages.edited': '✏️',
            'chats.update': '💬',
            'chats.upsert': '💬',
            'chats.delete': '🗑️',
            'chats.set': '⚙️',
            'connection.update': '🔗',
            'contacts.update': '👥',
            'contacts.upsert': '👤',
            'presence.update': '👁️',
            'qrcode.updated': '📱',
            'send.message': '📨',
            'group-participants.update': '👥',
            'labels.edit': '🏷️',
            'messages.set': '📝',
        }
        
        context = {
            'title': 'Monitoramento de Webhooks',
            'cache_stats': cache_stats,
            'events_by_type': events_by_type,
            'event_icons': event_icons,
            'recent_events_count': len(recent_events),
            'has_permission': True,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/connections/evolutionconnection/webhook_monitoring.html', context)
    
    @method_decorator(user_passes_test(is_superuser))
    @require_http_methods(["GET"])
    def webhook_monitoring_api(self, request):
        """API para obter dados do monitoramento de webhooks"""
        
        try:
            # Parâmetros de filtro
            event_type = request.GET.get('event_type', '')
            hours = int(request.GET.get('hours', 24))
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 50))
            
            # Obter eventos
            events = WebhookCache.list_recent_events(hours=hours)
            
            # Aplicar filtro por tipo de evento
            if event_type:
                filtered_events = []
                for event in events:
                    event_type_from_data = self._extract_event_type(event)
                    if event_type_from_data == event_type:
                        filtered_events.append(event)
                events = filtered_events
            
            # Aplicar paginação
            total_events = len(events)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_events = events[start_index:end_index]
            
            # Calcular informações de paginação
            total_pages = (total_events + page_size - 1) // page_size
            
            # Formatar eventos para resposta
            formatted_events = []
            for event in paginated_events:
                try:
                    formatted_event = self._format_event_for_display(event)
                    formatted_events.append(formatted_event)
                except Exception as e:
                    logger.warning(f"Erro ao formatar evento: {e}")
                    continue
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'events': formatted_events,
                    'pagination': {
                        'current_page': page,
                        'page_size': page_size,
                        'total_events': total_events,
                        'total_pages': total_pages,
                        'has_next': page < total_pages,
                        'has_previous': page > 1,
                    },
                    'filters': {
                        'event_type': event_type,
                        'hours': hours,
                    }
                }
            })
            
        except Exception as e:
            logger.error(f"Erro na API de monitoramento: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    def _extract_event_type(self, event):
        """Extrai o tipo do evento de forma flexível"""
        try:
            # Se é lista, pegar primeiro item
            if isinstance(event, list):
                event = event[0] if event else {}
            
            # Se é string, tentar fazer parse JSON
            if isinstance(event, str):
                try:
                    event = json.loads(event)
                except json.JSONDecodeError:
                    return None
            
            # Se tem campo 'data', usar ele
            if isinstance(event, dict) and 'data' in event:
                data_field = event['data']
                
                # Se data é string, tentar parse
                if isinstance(data_field, str):
                    try:
                        data_field = json.loads(data_field)
                    except json.JSONDecodeError:
                        data_field = {}
                
                # Buscar campo 'event' nos dados
                if isinstance(data_field, dict):
                    return data_field.get('event')
            
            # Se não tem campo 'data', buscar diretamente no evento
            if isinstance(event, dict):
                return event.get('event')
            
            return None
            
        except Exception as e:
            logger.warning(f"Erro ao extrair tipo do evento: {e}")
            return None
    
    def _format_event_for_display(self, event):
        """Formata evento para exibição"""
        try:
            # Extrair dados do evento
            event_data = self._extract_event_data(event)
            
            # Formatar para exibição
            formatted = {
                'id': event_data.get('id', ''),
                'event_type': event_data.get('event', 'unknown'),
                'instance': event_data.get('instance', ''),
                'timestamp': event_data.get('date_time', ''),
                'data': event_data,
                'formatted_timestamp': self._format_timestamp(event_data.get('date_time', '')),
                'formatted_data': self._format_event_data_for_display(event_data),
            }
            
            return formatted
            
        except Exception as e:
            logger.warning(f"Erro ao formatar evento para exibição: {e}")
            return {
                'id': 'error',
                'event_type': 'error',
                'instance': '',
                'timestamp': '',
                'data': {},
                'formatted_timestamp': 'Erro',
                'formatted_data': f'Erro ao processar: {str(e)}',
            }
    
    def _extract_event_data(self, event):
        """Extrai dados do evento de forma flexível"""
        try:
            # Se é lista, pegar primeiro item
            if isinstance(event, list):
                event = event[0] if event else {}
            
            # Se é string, tentar fazer parse JSON
            if isinstance(event, str):
                try:
                    event = json.loads(event)
                except json.JSONDecodeError:
                    return {}
            
            # Se tem campo 'data', usar ele
            if isinstance(event, dict) and 'data' in event:
                data_field = event['data']
                
                # Se data é string, tentar parse
                if isinstance(data_field, str):
                    try:
                        data_field = json.loads(data_field)
                    except json.JSONDecodeError:
                        data_field = {}
                
                # Mesclar dados do evento com dados internos
                result = event.copy()
                if isinstance(data_field, dict):
                    result.update(data_field)
                return result
            
            # Se não tem campo 'data', usar o objeto diretamente
            return event if isinstance(event, dict) else {}
            
        except Exception as e:
            logger.warning(f"Erro ao extrair dados do evento: {e}")
            return {}
    
    def _format_timestamp(self, timestamp_str):
        """Formata timestamp para exibição"""
        try:
            if not timestamp_str:
                return 'N/A'
            
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%d/%m/%Y %H:%M:%S')
            
        except Exception:
            return timestamp_str
    
    def _format_event_data_for_display(self, event_data):
        """Formata dados do evento para exibição"""
        try:
            # Criar resumo dos dados principais
            summary_parts = []
            
            # Adicionar campos importantes
            important_fields = ['message', 'contact', 'chat', 'instance', 'status', 'type']
            
            for field in important_fields:
                if field in event_data:
                    value = event_data[field]
                    if isinstance(value, dict):
                        # Para objetos, mostrar alguns campos principais
                        if field == 'message':
                            if 'body' in value:
                                summary_parts.append(f"Conteúdo: {value['body'][:50]}...")
                            if 'from' in value:
                                summary_parts.append(f"De: {value['from']}")
                        elif field == 'contact':
                            if 'name' in value:
                                summary_parts.append(f"Nome: {value['name']}")
                            if 'number' in value:
                                summary_parts.append(f"Telefone: {value['number']}")
                    else:
                        summary_parts.append(f"{field.title()}: {str(value)[:100]}")
            
            return ' | '.join(summary_parts) if summary_parts else 'Dados do evento'
            
        except Exception as e:
            return f'Erro ao formatar dados: {str(e)}'
