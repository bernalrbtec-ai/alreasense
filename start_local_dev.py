#!/usr/bin/env python
"""
Script para iniciar ambiente de desenvolvimento local
"""
import subprocess
import sys
import time
import requests
from datetime import datetime

def run_command(command, description):
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - Sucesso")
            return True
        else:
            print(f"❌ {description} - Erro:")
            print(f"   {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} - Exceção: {e}")
        return False

def check_service_health(url, service_name, timeout=30):
    print(f"🔍 Verificando {service_name}...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {service_name} está funcionando")
                return True
        except requests.exceptions.RequestException:
            pass
        
        time.sleep(2)
    
    print(f"❌ {service_name} não respondeu em {timeout}s")
    return False

def start_local_development():
    print("="*80)
    print("🚀 INICIANDO AMBIENTE DE DESENVOLVIMENTO LOCAL")
    print("="*80)
    print(f"⏰ Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    # 1. Parar containers existentes
    if not run_command("docker compose down", "Parando containers existentes"):
        print("⚠️ Continuando mesmo com erro ao parar containers...")
    
    # 2. Construir e iniciar containers
    print("\n🐳 Construindo e iniciando containers...")
    print("   Isso pode levar alguns minutos na primeira vez...")
    
    if not run_command("docker compose up --build -d", "Construindo e iniciando containers"):
        print("❌ Falha ao iniciar containers")
        return False
    
    # 3. Aguardar serviços ficarem prontos
    print("\n⏳ Aguardando serviços ficarem prontos...")
    time.sleep(10)
    
    # 4. Verificar saúde dos serviços
    print("\n🏥 Verificando saúde dos serviços...")
    
    services = [
        ("http://localhost:8000/api/health/", "Backend API"),
        ("http://localhost:80", "Frontend"),
    ]
    
    all_healthy = True
    for url, name in services:
        if not check_service_health(url, name, timeout=60):
            all_healthy = False
    
    # 5. Mostrar status final
    print("\n" + "="*80)
    print("📊 STATUS FINAL")
    print("="*80)
    
    if all_healthy:
        print("🎉 TODOS OS SERVIÇOS FUNCIONANDO!")
        print()
        print("📋 URLs disponíveis:")
        print("   • Frontend: http://localhost:80")
        print("   • Backend API: http://localhost:8000")
        print("   • Admin Django: http://localhost:8000/admin/")
        print()
        print("🧪 PRÓXIMOS PASSOS:")
        print("   1. Acesse: http://localhost:80")
        print("   2. Faça login com usuário de teste")
        print("   3. Teste o sistema de notificações")
        print("   4. Verifique se o menu aparece para usuários com acesso")
        print()
        print("🔧 COMANDOS ÚTEIS:")
        print("   • Ver logs: docker compose logs -f")
        print("   • Parar: docker compose down")
        print("   • Reiniciar: docker compose restart")
    else:
        print("❌ ALGUNS SERVIÇOS NÃO ESTÃO FUNCIONANDO")
        print()
        print("🔍 Para debugar:")
        print("   • Ver logs: docker compose logs -f")
        print("   • Verificar containers: docker compose ps")
        print("   • Reiniciar: docker compose restart")
    
    return all_healthy

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Uso: python start_local_dev.py")
        print("Inicia o ambiente de desenvolvimento local completo")
        return
    
    try:
        start_local_development()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrompido pelo usuário")
        print("Para parar os containers: docker compose down")
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        print("Para parar os containers: docker compose down")

if __name__ == '__main__':
    main()
