"""
Webhook Cache System - Redis + PostgreSQL Architecture
Armazena eventos webhook no Redis por 24h para reprocessamento
e persiste dados processados no PostgreSQL.
"""

import json
import logging
import redis
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ✅ IMPROVEMENT: Use correct Redis URL from settings
from django.conf import settings
redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
# ✅ IMPROVEMENT: Add connection pool for better performance
redis_client = redis.Redis.from_url(
    redis_url, 
    decode_responses=True,
    max_connections=50,  # Connection pooling
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True
)

class WebhookCache:
    """Sistema de cache para webhooks com TTL de 24h."""
    
    CACHE_PREFIX = "webhook"
    TTL_SECONDS = 86400  # 24 horas
    
    @classmethod
    def store_event(cls, event_id: str, event_data: Dict[Any, Any]) -> bool:
        """
        Armazena evento webhook no Redis por 24h.
        
        Args:
            event_id: ID único do evento
            event_data: Dados do evento webhook
            
        Returns:
            bool: True se armazenado com sucesso
        """
        try:
            # Adicionar timestamp de recebimento
            event_data['_cached_at'] = datetime.now(timezone.utc).isoformat()
            event_data['_event_id'] = event_id
            
            # Chave no Redis
            cache_key = f"{cls.CACHE_PREFIX}:{event_id}"
            
            # Armazenar no Redis com TTL de 24h
            redis_client.setex(
                cache_key, 
                cls.TTL_SECONDS, 
                json.dumps(event_data)
            )
            
            logger.info(f"📦 Evento armazenado no cache: {event_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao armazenar evento no cache: {str(e)}")
            return False
    
    @classmethod
    def get_event(cls, event_id: str) -> Optional[Dict[Any, Any]]:
        """
        Recupera evento webhook do Redis.
        
        Args:
            event_id: ID único do evento
            
        Returns:
            Dict com dados do evento ou None se não encontrado
        """
        try:
            cache_key = f"{cls.CACHE_PREFIX}:{event_id}"
            cached_data = redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao recuperar evento do cache: {str(e)}")
            return None
    
    @classmethod
    def list_recent_events(cls, hours: int = 24) -> list:
        """
        Lista eventos recentes do cache.
        
        Args:
            hours: Número de horas para buscar (padrão 24h)
            
        Returns:
            Lista de eventos encontrados
        """
        try:
            pattern = f"{cls.CACHE_PREFIX}:*"
            keys = redis_client.keys(pattern)
            
            events = []
            cutoff_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)
            
            for key in keys:
                event_data = redis_client.get(key)
                if event_data:
                    data = json.loads(event_data)
                    cached_at = data.get('_cached_at')
                    if cached_at:
                        event_time = datetime.fromisoformat(cached_at.replace('Z', '+00:00'))
                        if event_time.timestamp() > cutoff_time:
                            events.append(data)
            
            return sorted(events, key=lambda x: x.get('_cached_at', ''), reverse=True)
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar eventos recentes: {str(e)}")
            return []
    
    @classmethod
    def reprocess_events(cls, event_types: list = None) -> Dict[str, int]:
        """
        Reprocessa eventos do cache.
        
        Args:
            event_types: Lista de tipos de evento para reprocessar (None = todos)
            
        Returns:
            Dict com estatísticas de reprocessamento
        """
        try:
            events = cls.list_recent_events()
            stats = {
                'total': len(events),
                'processed': 0,
                'errors': 0,
                'by_type': {}
            }
            
            for event_data in events:
                event_type = event_data.get('event')
                
                # Filtrar por tipo se especificado
                if event_types and event_type not in event_types:
                    continue
                
                try:
                    # Reprocessar evento
                    from .webhook_views import EvolutionWebhookView
                    webhook_view = EvolutionWebhookView()
                    
                    # Simular request para reprocessamento
                    if event_type == 'messages.upsert':
                        webhook_view.handle_message_upsert(event_data)
                    elif event_type == 'messages.update':
                        webhook_view.handle_message_update(event_data)
                    elif event_type == 'connection.update':
                        webhook_view.handle_connection_update(event_data)
                    # ... outros tipos
                    
                    stats['processed'] += 1
                    stats['by_type'][event_type] = stats['by_type'].get(event_type, 0) + 1
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao reprocessar evento {event_data.get('_event_id')}: {str(e)}")
                    stats['errors'] += 1
            
            logger.info(f"🔄 Reprocessamento concluído: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Erro no reprocessamento: {str(e)}")
            return {'error': str(e)}
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """
        Retorna estatísticas do cache.
        
        Returns:
            Dict com estatísticas do Redis
        """
        try:
            pattern = f"{cls.CACHE_PREFIX}:*"
            keys = redis_client.keys(pattern)
            
            total_events = len(keys)
            total_memory = sum(redis_client.memory_usage(key) for key in keys)
            
            # Contar por tipo de evento
            event_types = {}
            for key in keys:
                event_data = redis_client.get(key)
                if event_data:
                    data = json.loads(event_data)
                    event_type = data.get('event', 'unknown')
                    event_types[event_type] = event_types.get(event_type, 0) + 1
            
            return {
                'total_events': total_events,
                'total_memory_bytes': total_memory,
                'event_types': event_types,
                'cache_ttl_hours': cls.TTL_SECONDS / 3600
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter estatísticas do cache: {str(e)}")
            return {'error': str(e)}


def generate_event_id(data: Dict[Any, Any]) -> str:
    """
    Gera ID único para evento webhook.
    
    Args:
        data: Dados do evento
        
    Returns:
        String com ID único
    """
    import hashlib
    import uuid
    
    # Usar dados do evento para gerar hash único
    event_string = f"{data.get('event', '')}_{data.get('instance', '')}_{data.get('server_url', '')}_{datetime.now(timezone.utc).isoformat()}"
    event_hash = hashlib.md5(event_string.encode()).hexdigest()[:8]
    
    return f"{event_hash}_{uuid.uuid4().hex[:8]}"
