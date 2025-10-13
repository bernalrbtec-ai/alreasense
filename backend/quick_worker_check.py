#!/usr/bin/env python
"""
Script rápido para verificar status dos workers
"""
import os
import sys

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
import django
django.setup()

def quick_check():
    """Verificação rápida dos workers"""
    print("⚡ VERIFICAÇÃO RÁPIDA DOS WORKERS")
    print("=" * 40)
    
    try:
        # 1. Verificar Celery
        from alrea_sense.celery import app
        print("✅ Celery app carregado")
        
        # 2. Verificar workers ativos
        inspect = app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            print(f"✅ {len(active_workers)} worker(s) ativo(s):")
            for worker_name in active_workers.keys():
                print(f"   🔧 {worker_name}")
        else:
            print("❌ Nenhum worker ativo")
        
        # 3. Verificar Redis
        import redis
        redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()
        print("✅ Redis conectado")
        
        # 4. Verificar filas
        queue_length = r.llen('celery:celery')
        print(f"📋 Tasks na fila: {queue_length}")
        
        # 5. Verificar campanhas
        from apps.campaigns.models import Campaign
        active_campaigns = Campaign.objects.filter(status='running').count()
        print(f"📧 Campanhas ativas: {active_campaigns}")
        
        print("\n🎯 Status: TUDO OK!" if active_workers and active_campaigns == 0 or queue_length == 0 else "\n⚠️  Status: ATENÇÃO - Workers ativos ou fila com tasks")
        
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    quick_check()
