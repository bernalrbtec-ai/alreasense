#!/usr/bin/env python
"""
Script para monitorar workers do Celery
Mostra status dos workers, tasks em execução, filas e estatísticas
"""
import os
import sys
import time
import json
from datetime import datetime, timedelta

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
import django
django.setup()

def get_redis_connection():
    """Conecta ao Redis para monitoramento"""
    try:
        import redis
        redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()  # Testar conexão
        return r
    except Exception as e:
        print(f"❌ Erro ao conectar Redis: {e}")
        return None

def get_celery_app():
    """Obtém a instância do Celery"""
    try:
        from alrea_sense.celery import app
        return app
    except Exception as e:
        print(f"❌ Erro ao obter Celery app: {e}")
        return None

def monitor_workers():
    """Monitora workers do Celery"""
    print("🔍 MONITOR DE WORKERS CELERY")
    print("=" * 50)
    
    # Conectar ao Redis
    redis_client = get_redis_connection()
    if not redis_client:
        return
    
    # Obter Celery app
    celery_app = get_celery_app()
    if not celery_app:
        return
    
    try:
        # 1. Status dos Workers
        print("\n👥 STATUS DOS WORKERS:")
        print("-" * 30)
        
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        stats = inspect.stats()
        
        if active_workers:
            for worker_name, tasks in active_workers.items():
                print(f"✅ {worker_name}")
                print(f"   Tasks ativas: {len(tasks)}")
                
                # Mostrar tasks ativas
                for task in tasks:
                    task_name = task.get('name', 'Unknown')
                    task_id = task.get('id', 'Unknown')
                    print(f"   📋 {task_name} (ID: {task_id[:8]}...)")
                
                # Mostrar estatísticas do worker
                if stats and worker_name in stats:
                    worker_stats = stats[worker_name]
                    total_tasks = worker_stats.get('total', {})
                    print(f"   📊 Total tasks processadas: {sum(total_tasks.values())}")
        else:
            print("❌ Nenhum worker ativo encontrado")
        
        # 2. Filas do Celery
        print("\n📋 FILAS DO CELERY:")
        print("-" * 30)
        
        # Verificar filas principais
        queues = ['celery', 'campaigns', 'default']
        for queue_name in queues:
            try:
                queue_length = redis_client.llen(f"celery:{queue_name}")
                print(f"🔄 {queue_name}: {queue_length} tasks pendentes")
            except:
                print(f"❌ {queue_name}: Erro ao verificar")
        
        # 3. Tasks Recentes
        print("\n📈 TASKS RECENTES:")
        print("-" * 30)
        
        # Buscar tasks recentes no Redis
        recent_tasks = []
        for key in redis_client.scan_iter(match="celery-task-meta-*"):
            try:
                task_data = redis_client.get(key)
                if task_data:
                    task_info = json.loads(task_data)
                    if task_info.get('status') in ['SUCCESS', 'FAILURE']:
                        recent_tasks.append({
                            'id': key.decode().split('-')[-1],
                            'status': task_info.get('status'),
                            'result': task_info.get('result'),
                            'date_done': task_info.get('date_done')
                        })
            except:
                continue
        
        # Ordenar por data (mais recentes primeiro)
        recent_tasks.sort(key=lambda x: x.get('date_done', ''), reverse=True)
        
        for task in recent_tasks[:5]:  # Mostrar apenas as 5 mais recentes
            status_emoji = "✅" if task['status'] == 'SUCCESS' else "❌"
            task_id = task['id'][:8] + "..."
            date_done = task.get('date_done', 'Unknown')
            
            print(f"{status_emoji} {task_id} - {task['status']}")
            if date_done != 'Unknown':
                try:
                    dt = datetime.fromisoformat(date_done.replace('Z', '+00:00'))
                    print(f"   🕒 {dt.strftime('%H:%M:%S')}")
                except:
                    print(f"   🕒 {date_done}")
        
        # 4. Estatísticas do Sistema
        print("\n📊 ESTATÍSTICAS DO SISTEMA:")
        print("-" * 30)
        
        # Informações do Redis
        redis_info = redis_client.info()
        print(f"🔴 Redis:")
        print(f"   Uso de memória: {redis_info.get('used_memory_human', 'Unknown')}")
        print(f"   Conexões ativas: {redis_info.get('connected_clients', 'Unknown')}")
        
        # Verificar campanhas ativas
        try:
            from apps.campaigns.models import Campaign
            active_campaigns = Campaign.objects.filter(status='running').count()
            total_campaigns = Campaign.objects.count()
            print(f"📧 Campanhas:")
            print(f"   Ativas: {active_campaigns}")
            print(f"   Total: {total_campaigns}")
        except Exception as e:
            print(f"❌ Erro ao verificar campanhas: {e}")
        
        # 5. Health Check
        print("\n🏥 HEALTH CHECK:")
        print("-" * 30)
        
        # Testar conexão com banco
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            print("✅ Database: OK")
        except Exception as e:
            print(f"❌ Database: {e}")
        
        # Testar Redis
        try:
            redis_client.ping()
            print("✅ Redis: OK")
        except Exception as e:
            print(f"❌ Redis: {e}")
        
        # Testar Celery
        try:
            celery_app.control.ping(timeout=1)
            print("✅ Celery: OK")
        except Exception as e:
            print(f"❌ Celery: {e}")
        
        print(f"\n🕒 Última verificação: {datetime.now().strftime('%H:%M:%S')}")
        
    except Exception as e:
        print(f"❌ Erro durante monitoramento: {e}")

def monitor_continuous(interval=10):
    """Monitora workers continuamente"""
    print(f"🔄 Iniciando monitoramento contínuo (intervalo: {interval}s)")
    print("Pressione Ctrl+C para parar\n")
    
    try:
        while True:
            # Limpar tela (funciona no Windows e Linux)
            os.system('cls' if os.name == 'nt' else 'clear')
            
            monitor_workers()
            
            print(f"\n⏳ Próxima verificação em {interval} segundos...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitoramento interrompido pelo usuário")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        monitor_continuous(interval)
    else:
        monitor_workers()
