#!/usr/bin/env python
"""
Script para monitorar workers remotos do Railway
"""
import os
import sys
import requests
import json
from datetime import datetime

def monitor_remote():
    """Monitora workers remotos via API"""
    print("🌐 MONITOR DE WORKERS REMOTOS (RAILWAY)")
    print("=" * 50)
    
    # URLs do Railway
    backend_url = "https://alreasense-backend-production.up.railway.app"
    
    try:
        # 1. Health Check
        print("\n🏥 HEALTH CHECK:")
        print("-" * 30)
        
        try:
            response = requests.get(f"{backend_url}/api/health/", timeout=10)
            if response.status_code == 200:
                print("✅ Backend: OK")
            else:
                print(f"⚠️  Backend: Status {response.status_code}")
        except Exception as e:
            print(f"❌ Backend: {e}")
        
        # 2. Verificar campanhas ativas
        print("\n📧 CAMPANHAS:")
        print("-" * 30)
        
        try:
            response = requests.get(f"{backend_url}/api/campaigns/", timeout=10)
            if response.status_code == 200:
                campaigns = response.json()
                
                if 'results' in campaigns:
                    campaigns_list = campaigns['results']
                else:
                    campaigns_list = campaigns if isinstance(campaigns, list) else []
                
                running_campaigns = [c for c in campaigns_list if c.get('status') == 'running']
                total_campaigns = len(campaigns_list)
                
                print(f"📊 Total de campanhas: {total_campaigns}")
                print(f"🏃 Campanhas em execução: {len(running_campaigns)}")
                
                if running_campaigns:
                    print("\n📋 Campanhas ativas:")
                    for campaign in running_campaigns:
                        name = campaign.get('name', 'Sem nome')[:30]
                        progress = campaign.get('progress_percentage', 0)
                        print(f"   🔄 {name}... ({progress:.1f}%)")
                
            else:
                print(f"❌ Erro ao buscar campanhas: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro ao verificar campanhas: {e}")
        
        # 3. Verificar instâncias WhatsApp
        print("\n📱 INSTÂNCIAS WHATSAPP:")
        print("-" * 30)
        
        try:
            response = requests.get(f"{backend_url}/api/connections/instances/", timeout=10)
            if response.status_code == 200:
                instances = response.json()
                
                if 'results' in instances:
                    instances_list = instances['results']
                else:
                    instances_list = instances if isinstance(instances, list) else []
                
                active_instances = [i for i in instances_list if i.get('connection_state') == 'open']
                
                print(f"📊 Total de instâncias: {len(instances_list)}")
                print(f"✅ Instâncias conectadas: {len(active_instances)}")
                
                if active_instances:
                    print("\n📋 Instâncias ativas:")
                    for instance in active_instances:
                        name = instance.get('friendly_name', 'Sem nome')
                        health = instance.get('health_score', 0)
                        status = "🟢" if health >= 80 else "🟡" if health >= 50 else "🔴"
                        print(f"   {status} {name} (Health: {health}%)")
                
            else:
                print(f"❌ Erro ao buscar instâncias: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro ao verificar instâncias: {e}")
        
        # 4. Verificar mensagens recentes
        print("\n💬 MENSAGENS RECENTES:")
        print("-" * 30)
        
        try:
            response = requests.get(f"{backend_url}/api/messages/?page_size=5", timeout=10)
            if response.status_code == 200:
                messages = response.json()
                
                if 'results' in messages:
                    messages_list = messages['results']
                else:
                    messages_list = messages if isinstance(messages, list) else []
                
                print(f"📊 Total de mensagens recentes: {len(messages_list)}")
                
                if messages_list:
                    print("\n📋 Últimas mensagens:")
                    for msg in messages_list[:3]:
                        sender = msg.get('sender_name', 'Desconhecido')
                        content = msg.get('content', 'Sem conteúdo')[:30]
                        created = msg.get('created_at', '')
                        
                        if created:
                            try:
                                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                                time_str = dt.strftime('%H:%M:%S')
                            except:
                                time_str = created
                        else:
                            time_str = 'N/A'
                        
                        print(f"   💬 {sender}: {content}... ({time_str})")
                
            else:
                print(f"❌ Erro ao buscar mensagens: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro ao verificar mensagens: {e}")
        
        print(f"\n🕒 Verificação realizada: {datetime.now().strftime('%H:%M:%S')}")
        print("🌐 Monitorando: Railway Production")
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")

def monitor_local():
    """Monitora workers locais"""
    print("🏠 MONITOR DE WORKERS LOCAIS")
    print("=" * 40)
    
    # Configurar Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
    import django
    django.setup()
    
    try:
        from alrea_sense.celery import app
        
        # Verificar workers
        inspect = app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            print(f"✅ {len(active_workers)} worker(s) local(is):")
            for worker_name in active_workers.keys():
                print(f"   🔧 {worker_name}")
        else:
            print("❌ Nenhum worker local ativo")
            print("💡 Execute: celery -A alrea_sense worker -l info")
        
    except Exception as e:
        print(f"❌ Erro ao verificar workers locais: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--local":
        monitor_local()
    else:
        monitor_remote()
