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
            'memory_usage': info.get('used_memory_human', 'N/A'),
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


def check_rabbitmq():
    """Check RabbitMQ server connectivity (broker), not the campaign consumer."""
    try:
        rabbitmq_url = getattr(settings, 'RABBITMQ_URL', None)
        if not rabbitmq_url:
            return {
                'status': 'not_configured',
                'message': 'RABBITMQ_URL não configurada',
                'consumer_running': False,
            }
        import pika
        params = pika.URLParameters(rabbitmq_url)
        params.socket_timeout = 5
        params.blocked_connection_timeout = 5
        conn = pika.BlockingConnection(params)
        conn.close()
        # Broker is reachable = healthy; consumer info is optional for display
        consumer_running = False
        active_threads = 0
        try:
            from apps.campaigns.rabbitmq_consumer import get_rabbitmq_consumer
            c = get_rabbitmq_consumer()
            if c:
                consumer_running = getattr(c, 'running', False)
                active_threads = len(getattr(c, 'consumer_threads', {}) or {})
        except Exception:
            pass
        return {
            'status': 'healthy',
            'connection': True,
            'channel': True,
            'consumer_running': consumer_running,
            'active_campaign_threads': active_threads,
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)[:150],
            'connection': False,
            'channel': False,
            'consumer_running': False,
        }


def check_evolution_api():
    """Check Evolution API connectivity and registered instances (WhatsAppInstance = cadastradas no Sense)."""
    try:
        from apps.notifications.models import WhatsAppInstance

        # Instâncias cadastradas no Sense (WhatsAppInstance)
        total_count = WhatsAppInstance.objects.count()
        active_count = WhatsAppInstance.objects.filter(is_active=True).count()
        inactive_count = total_count - active_count

        api_status = 'disconnected'
        external_count = 0

        try:
            evolution_url = getattr(settings, 'EVOLUTION_API_URL', None) or getattr(settings, 'EVO_BASE_URL', '')
            evolution_key = getattr(settings, 'EVOLUTION_API_KEY', None) or getattr(settings, 'EVO_API_KEY', '')

            if evolution_url and evolution_key and 'SEU_' not in str(evolution_key):
                headers = {
                    'apikey': evolution_key,
                    'Content-Type': 'application/json'
                }
                test_url = f"{evolution_url.rstrip('/')}/instance/fetchInstances"
                response = requests.get(test_url, headers=headers, timeout=3)

                if response.status_code == 200:
                    data = response.json()
                    external_count = len(data) if isinstance(data, list) else 0
                    api_status = 'connected'
                else:
                    api_status = 'error'
            else:
                api_status = 'no_active_connection'

        except Exception:
            api_status = 'disconnected'

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
            'registered_instances': {'total': 0, 'active': 0, 'inactive': 0},
            'external_api_instances': 0,
            'api_connectivity': 'error'
        }


def _human_size(size_bytes):
    """Format bytes to human-readable (e.g. 1.5 GB)."""
    if size_bytes is None or size_bytes < 0:
        return 'N/A'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}' if unit != 'B' else f'{size_bytes} B'
        size_bytes /= 1024
    return f'{size_bytes:.1f} PB'


def check_minio():
    """Check MinIO/S3 storage connectivity and bucket usage."""
    try:
        endpoint = getattr(settings, 'S3_ENDPOINT_URL', None) or ''
        access = getattr(settings, 'S3_ACCESS_KEY', None) or ''
        secret = getattr(settings, 'S3_SECRET_KEY', None) or ''
        bucket = getattr(settings, 'S3_BUCKET', '') or ''

        if not endpoint or not access or not secret or not bucket:
            return {
                'status': 'not_configured',
                'message': 'MinIO/S3 não configurado (S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET)'
            }

        import boto3
        from botocore.config import Config

        client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            region_name=getattr(settings, 'S3_REGION', 'us-east-1'),
            config=Config(signature_version='s3v4', s3={'addressing_style': 'path'})
        )
        client.head_bucket(Bucket=bucket)

        # Calcular uso do bucket (soma dos tamanhos; limitado a 50 páginas para não travar)
        total_bytes = 0
        try:
            paginator = client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket, MaxKeys=1000)
            for i, page in enumerate(pages):
                if i >= 50:
                    break
                for obj in page.get('Contents') or []:
                    total_bytes += obj.get('Size') or 0
        except Exception:
            total_bytes = None

        result = {
            'status': 'healthy',
            'bucket': bucket,
        }
        if total_bytes is not None:
            result['bucket_size_bytes'] = total_bytes
            result['bucket_size_human'] = _human_size(total_bytes)
        return result
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)[:150]
        }


def get_system_health():
    """Get comprehensive system health status."""
    db_status = check_database()
    redis_status = check_redis()
    rabbitmq_status = check_rabbitmq()
    evolution_status = check_evolution_api()
    minio_status = check_minio()

    # Status geral: saudável só se DB, Redis e RabbitMQ estiverem ok (MinIO opcional)
    critical_ok = (
        db_status.get('status') == 'healthy'
        and redis_status.get('status') == 'healthy'
        and rabbitmq_status.get('status') == 'healthy'
    )
    overall_healthy = critical_ok

    return {
        'status': 'healthy' if overall_healthy else 'degraded',
        'database': db_status,
        'redis': redis_status,
        'rabbitmq': rabbitmq_status,
        'evolution_api': evolution_status,
        'minio': minio_status,
        'services': {
            'database': db_status.get('status'),
            'redis': redis_status.get('status'),
            'rabbitmq': rabbitmq_status.get('status'),
            'evolution_api': evolution_status.get('status'),
            'minio': minio_status.get('status'),
        }
    }

