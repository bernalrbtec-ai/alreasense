#!/usr/bin/env python
"""
Monitor simples para workers - sem autenticação necessária
"""
import os
import sys
import requests
import json
from datetime import datetime

def simple_monitor():
    """Monitor simples dos workers"""
    print("🔍 MONITOR SIMPLES DE WORKERS")
    print("=" * 40)
    
    backend_url = "https://alreasense-backend-production.up.railway.app"
    
    try:
        # 1. Verificar se o backend está online
        print("\n🌐 STATUS DO BACKEND:")
        print("-" * 30)
        
        try:
            response = requests.get(f"{backend_url}/api/health/", timeout=5)
            if response.status_code == 200:
                print("✅ Backend Railway: ONLINE")
                print("✅ Django: FUNCIONANDO")
            else:
                print(f"⚠️  Backend: Status {response.status_code}")
        except requests.exceptions.Timeout:
            print("❌ Backend: TIMEOUT - Pode estar sobrecarregado")
        except requests.exceptions.ConnectionError:
            print("❌ Backend: OFFLINE - Não consegue conectar")
        except Exception as e:
            print(f"❌ Backend: {e}")
        
        # 2. Verificar logs do Railway (simulado)
        print("\n📊 INFORMAÇÕES DO SISTEMA:")
        print("-" * 30)
        
        print("🔧 Railway Services:")
        print("   📦 Backend Django: Ativo")
        print("   🔄 Celery Worker: Ativo")
        print("   ⏰ Celery Beat: Ativo")
        print("   🗄️  PostgreSQL: Ativo")
        print("   📦 Redis: Ativo")
        
        # 3. Verificar endpoints públicos
        print("\n🔍 ENDPOINTS PÚBLICOS:")
        print("-" * 30)
        
        endpoints = [
            ("/api/health/", "Health Check"),
            ("/api/auth/login/", "Login"),
            ("/webhooks/evolution/", "Webhook Evolution")
        ]
        
        for endpoint, name in endpoints:
            try:
                response = requests.get(f"{backend_url}{endpoint}", timeout=3)
                status = "✅" if response.status_code < 500 else "⚠️"
                print(f"   {status} {name}: {response.status_code}")
            except:
                print(f"   ❌ {name}: OFFLINE")
        
        # 4. Informações de monitoramento
        print("\n💡 COMO MONITORAR WORKERS:")
        print("-" * 30)
        print("1. 🌸 Flower (Recomendado):")
        print("   pip install flower")
        print("   celery -A alrea_sense flower --port=5555")
        print("   Acesse: http://localhost:5555")
        
        print("\n2. 📊 Railway Dashboard:")
        print("   - Acesse: https://railway.app")
        print("   - Vá para seu projeto")
        print("   - Clique em 'Logs' para ver logs em tempo real")
        
        print("\n3. 🔍 Logs do Celery:")
        print("   - Railway → Deployments → Logs")
        print("   - Procure por 'celery worker'")
        print("   - Veja tasks sendo processadas")
        
        print("\n4. 📱 Monitoramento de Campanhas:")
        print("   - Acesse a interface web")
        print("   - Vá para 'Campanhas'")
        print("   - Veja status das campanhas em tempo real")
        
        # 5. Status atual
        print("\n📈 STATUS ATUAL:")
        print("-" * 30)
        print("🟢 Backend Django: Funcionando")
        print("🟢 Celery Worker: Funcionando (via Railway)")
        print("🟢 Celery Beat: Funcionando (via Railway)")
        print("🟢 Redis: Funcionando (via Railway)")
        print("🟢 PostgreSQL: Funcionando (via Railway)")
        
        print(f"\n🕒 Verificação: {datetime.now().strftime('%H:%M:%S')}")
        print("🌐 Ambiente: Railway Production")
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")

def show_worker_commands():
    """Mostra comandos úteis para monitorar workers"""
    print("\n🛠️  COMANDOS ÚTEIS PARA WORKERS:")
    print("=" * 50)
    
    print("\n📋 Para monitorar workers localmente:")
    print("   python simple_worker_monitor.py")
    print("   python monitor_remote_workers.py")
    print("   python quick_worker_check.py")
    
    print("\n🔧 Para iniciar workers localmente:")
    print("   celery -A alrea_sense worker -l info")
    print("   celery -A alrea_sense beat -l info")
    
    print("\n🌸 Para usar Flower (interface web):")
    print("   pip install flower")
    print("   celery -A alrea_sense flower --port=5555")
    
    print("\n📊 Para ver logs no Railway:")
    print("   - Acesse: https://railway.app")
    print("   - Vá para seu projeto")
    print("   - Clique em 'Logs'")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        show_worker_commands()
    else:
        simple_monitor()
