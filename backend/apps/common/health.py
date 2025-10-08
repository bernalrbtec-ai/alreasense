"""
Health check utilities for system status monitoring.
"""
import redis
from django.db import connection
from django.conf import settings
from celery import current_app
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
        redis_url = settings.CELERY_BROKER_URL
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


def check_celery():
    """Check Celery worker status."""
    try:
        inspect = current_app.control.inspect()
        stats = inspect.stats()
        active = inspect.active()
        
        if not stats:
            return {
                'status': 'unhealthy',
                'error': 'No workers available'
            }
        
        active_tasks = 0
        if active:
            for worker_tasks in active.values():
                active_tasks += len(worker_tasks)
        
        return {
            'status': 'healthy',
            'workers': len(stats) if stats else 0,
            'active_tasks': active_tasks,
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


def check_evolution_api():
    """Check Evolution API connectivity."""
    try:
        from apps.connections.models import EvolutionConnection
        
        # Get first active connection (or create default)
        base_url = settings.EVO_BASE_URL if hasattr(settings, 'EVO_BASE_URL') else 'https://evo.rbtec.com.br'
        api_key = settings.EVO_API_KEY if hasattr(settings, 'EVO_API_KEY') else '584B4A4A-0815-AC86-DC39-C38FC27E8E17'
        
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        
        test_url = f"{base_url}/instance/fetchInstances"
        response = requests.get(test_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            instances = response.json()
            
            # Count registered instances in our database
            # For now, we'll just return 0 since we haven't implemented instance registration yet
            registered_count = 0
            active_count = 0
            inactive_count = 0
            
            return {
                'status': 'active',
                'instance_count': len(instances),
                'registered_instances': {
                    'total': registered_count,
                    'active': active_count,
                    'inactive': inactive_count,
                }
            }
        else:
            return {
                'status': 'error',
                'error': f'HTTP {response.status_code}'
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)[:100]
        }


def get_system_health():
    """Get comprehensive system health status."""
    db_status = check_database()
    redis_status = check_redis()
    celery_status = check_celery()
    evolution_status = check_evolution_api()
    
    # Overall status is healthy only if all services are healthy
    overall_healthy = all([
        db_status.get('status') == 'healthy',
        redis_status.get('status') == 'healthy',
    ])
    
    return {
        'status': 'healthy' if overall_healthy else 'degraded',
        'database': db_status,
        'redis': redis_status,
        'celery': celery_status,
        'evolution_api': evolution_status,
        'services': {
            'database': db_status.get('status'),
            'redis': redis_status.get('status'),
            'celery': celery_status.get('status'),
            'evolution_api': evolution_status.get('status'),
        }
    }

