#!/usr/bin/env python
"""
Script principal para desenvolvimento local
"""
import sys
import subprocess
import os

def show_help():
    print("="*80)
    print("🚀 ALREA SENSE - DESENVOLVIMENTO LOCAL")
    print("="*80)
    print("Uso: python dev.py [comando]")
    print()
    print("Comandos disponíveis:")
    print("  start     - Iniciar ambiente completo (Docker + dados)")
    print("  start-prod-db - Iniciar local com banco de produção")
    print("  stop      - Parar todos os containers")
    print("  restart   - Reiniciar ambiente")
    print("  logs      - Ver logs dos containers")
    print("  status    - Ver status dos containers")
    print("  setup     - Configurar banco com dados de teste")
    print("  clean     - Limpar containers e volumes")
    print("  help      - Mostrar esta ajuda")
    print()
    print("Exemplos:")
    print("  python dev.py start")
    print("  python dev.py logs")
    print("  python dev.py setup")

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

def start_environment():
    print("="*80)
    print("🚀 INICIANDO AMBIENTE DE DESENVOLVIMENTO")
    print("="*80)
    
    # 1. Parar containers existentes
    run_command("docker compose down", "Parando containers existentes")
    
    # 2. Construir e iniciar
    if not run_command("docker compose up --build -d", "Construindo e iniciando containers"):
        return False
    
    # 3. Aguardar serviços ficarem prontos
    print("⏳ Aguardando serviços ficarem prontos...")
    import time
    time.sleep(15)
    
    # 4. Configurar banco
    print("\n🗄️ Configurando banco com dados de teste...")
    if not run_command("python setup_local_database.py", "Configurando banco"):
        print("⚠️ Erro ao configurar banco, mas continuando...")
    
    print("\n🎉 AMBIENTE INICIADO COM SUCESSO!")
    print("📋 URLs disponíveis:")
    print("   • Frontend: http://localhost:80")
    print("   • Backend: http://localhost:8000")
    print("   • Admin: http://localhost:8000/admin/")
    print()
    print("👤 Login de teste:")
    print("   • Email: admin@teste.local")
    print("   • Senha: admin123")
    
    return True

def stop_environment():
    print("="*80)
    print("🛑 PARANDO AMBIENTE")
    print("="*80)
    
    return run_command("docker compose down", "Parando containers")

def restart_environment():
    print("="*80)
    print("🔄 REINICIANDO AMBIENTE")
    print("="*80)
    
    stop_environment()
    return start_environment()

def show_logs():
    print("="*80)
    print("📋 LOGS DOS CONTAINERS")
    print("="*80)
    
    return run_command("docker compose logs -f", "Mostrando logs")

def show_status():
    print("="*80)
    print("📊 STATUS DOS CONTAINERS")
    print("="*80)
    
    return run_command("docker compose ps", "Mostrando status")

def setup_database():
    print("="*80)
    print("🗄️ CONFIGURANDO BANCO")
    print("="*80)
    
    return run_command("python setup_local_database.py", "Configurando banco com dados de teste")

def clean_environment():
    print("="*80)
    print("🧹 LIMPANDO AMBIENTE")
    print("="*80)
    
    print("⚠️ Isso irá remover todos os containers, volumes e dados!")
    response = input("Tem certeza? (digite 'sim' para confirmar): ")
    
    if response.lower() != 'sim':
        print("❌ Operação cancelada")
        return False
    
    commands = [
        ("docker compose down -v", "Parando containers e removendo volumes"),
        ("docker system prune -f", "Limpando sistema Docker"),
        ("docker volume prune -f", "Removendo volumes não utilizados"),
    ]
    
    for command, description in commands:
        run_command(command, description)
    
    print("✅ Ambiente limpo com sucesso!")
    return True

def start_production_db_environment():
    print("="*80)
    print("🚀 INICIANDO AMBIENTE LOCAL COM BANCO DE PRODUÇÃO")
    print("="*80)
    
    # 1. Configurar ambiente
    if not run_command("python setup_local_with_production_db.py setup", "Configurando ambiente com banco de produção"):
        return False
    
    # 2. Parar containers existentes
    run_command("docker compose down", "Parando containers existentes")
    
    # 3. Construir e iniciar (sem banco local)
    if not run_command("docker compose -f docker-compose.prod-db.yml up --build -d", "Construindo e iniciando containers"):
        return False
    
    # 4. Aguardar serviços
    print("⏳ Aguardando serviços ficarem prontos...")
    import time
    time.sleep(15)
    
    print("\n🎉 AMBIENTE INICIADO COM BANCO DE PRODUÇÃO!")
    print("📋 URLs disponíveis:")
    print("   • Frontend: http://localhost:80")
    print("   • Backend: http://localhost:8000")
    print("   • Admin: http://localhost:8000/admin/")
    print()
    print("👤 Login com usuários de produção:")
    print("   • paulo.bernal@alrea.ai")
    print("   • paulo.bernal@rbtec.com.br")
    print("   • thiago-bal@hotmail.com")
    print()
    print("⚠️ ATENÇÃO: Você está usando dados REAIS de produção!")
    
    return True

def main():
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "help":
        show_help()
    elif command == "start":
        start_environment()
    elif command == "start-prod-db":
        start_production_db_environment()
    elif command == "stop":
        stop_environment()
    elif command == "restart":
        restart_environment()
    elif command == "logs":
        show_logs()
    elif command == "status":
        show_status()
    elif command == "setup":
        setup_database()
    elif command == "clean":
        clean_environment()
    else:
        print(f"❌ Comando desconhecido: {command}")
        show_help()

if __name__ == '__main__':
    main()
