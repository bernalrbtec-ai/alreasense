"""
Health check utilities for system status monitoring.
"""
import redis
from django.db import connection
from django.conf import settings
import requests


def check_database():
    """Check database connectivity."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        # Get connection count
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT count(*) 
                FROM pg_stat_activity 
                WHERE datname = current_database()
            """)
            connection_count = cursor.fetchone()[0]
        
        return {
            'status': 'healthy',
            'connection_count': connection_count,
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


def check_redis():
    """Check Redis connectivity."""
    try:
        redis_url = getattr(settings, 'REDIS_URL', None)
        if not redis_url:
            return {
                'status': 'not_configured',
                'message': 'Redis not configured'
            }
        
        r = redis.from_url(redis_url)
        r.ping()
        
        info = r.info()
        
        return {
            'status': 'healthy',
            'connected_clients': info.get('connected_clients', 0),
            'used_memory_human': info.get('used_memory_human', 'N/A'),
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


def check_rabbitmq():
    """Check RabbitMQ connectivity."""
    try:
        from apps.campaigns.rabbitmq_consumer import rabbitmq_consumer
        
        # Check if consumer is running
        active_campaigns = rabbitmq_consumer.get_active_campaigns()
        
        return {
            'status': 'healthy',
            'active_campaigns': len(active_campaigns),
            'consumer_running': True,
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


def check_evolution_api():
    """Check Evolution API connectivity and registered instances."""
    try:
        from apps.connections.models import EvolutionConnection
        
        # Count instances registered in our database
        all_connections = EvolutionConnection.objects.all()
        total_count = all_connections.count()
        active_count = all_connections.filter(status='active', is_active=True).count()
        inactive_count = all_connections.filter(status='inactive').count()
        
        # Try to check external API connectivity using registered connections
        api_status = 'disconnected'
        external_count = 0
        
        try:
            # Use the first active connection from database
            active_connection = all_connections.filter(is_active=True).first()
            
            if active_connection and active_connection.base_url and active_connection.api_key:
                headers = {
                    'apikey': active_connection.api_key,
                    'Content-Type': 'application/json'
                }
                
                # Test connectivity with the registered connection
                test_url = f"{active_connection.base_url}/instance/fetchInstances"
                response = requests.get(test_url, headers=headers, timeout=3)
                
                if response.status_code == 200:
                    external_instances = response.json()
                    api_status = 'connected'
                    external_count = len(external_instances)
                else:
                    api_status = 'error'
                    external_count = 0
            else:
                api_status = 'no_active_connection'
                external_count = 0
                
        except Exception:
            api_status = 'disconnected'
            external_count = 0
        
        return {
            'status': api_status,
            'registered_instances': {
                'total': total_count,
                'active': active_count,
                'inactive': inactive_count,
            },
            'external_api_instances': external_count,
            'api_connectivity': api_status
        }
            
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)[:100],
            'registered_instances': {
                'total': 0,
                'active': 0,
                'inactive': 0,
            },
            'external_api_instances': 0,
            'api_connectivity': 'error'
        }


def get_system_health():
    """Get comprehensive system health status."""
    db_status = check_database()
    redis_status = check_redis()
    rabbitmq_status = check_rabbitmq()
    evolution_status = check_evolution_api()
    
    # Overall status is healthy only if all services are healthy
    overall_healthy = all([
        db_status.get('status') == 'healthy',
        rabbitmq_status.get('status') == 'healthy',
    ])
    
    return {
        'status': 'healthy' if overall_healthy else 'degraded',
        'database': db_status,
        'redis': redis_status,
        'rabbitmq': rabbitmq_status,
        'evolution_api': evolution_status,
        'services': {
            'database': db_status.get('status'),
            'redis': redis_status.get('status'),
            'rabbitmq': rabbitmq_status.get('status'),
            'evolution_api': evolution_status.get('status'),
        }
    }

