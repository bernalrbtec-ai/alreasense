#!/usr/bin/env python
"""
Script para configurar ambiente local
"""
import os
import subprocess
import sys

def setup_local_environment():
    print("="*80)
    print("🔧 CONFIGURANDO AMBIENTE LOCAL")
    print("="*80)
    
    # 1. Verificar se Docker está rodando
    print("\n🐳 Verificando Docker...")
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✅ Docker: {result.stdout.strip()}")
        else:
            print("   ❌ Docker não encontrado")
            return False
    except FileNotFoundError:
        print("   ❌ Docker não instalado")
        return False
    
    # 2. Verificar se Docker Compose está disponível
    print("\n🐳 Verificando Docker Compose...")
    try:
        result = subprocess.run(['docker', 'compose', 'version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✅ Docker Compose: {result.stdout.strip()}")
        else:
            print("   ❌ Docker Compose não encontrado")
            return False
    except FileNotFoundError:
        print("   ❌ Docker Compose não instalado")
        return False
    
    # 3. Verificar arquivos de ambiente
    print("\n📝 Verificando arquivos de ambiente...")
    env_local = "backend/.env"
    env_railway = "backend/.env.railway"
    
    if os.path.exists(env_local):
        print(f"   ✅ Arquivo {env_local} já existe (local)")
    else:
        print(f"   ❌ Arquivo {env_local} não encontrado")
    
    if os.path.exists(env_railway):
        print(f"   ✅ Arquivo {env_railway} já existe (Railway)")
    else:
        print(f"   ⚠️ Arquivo {env_railway} não encontrado (criar se necessário)")
    
    print("   📋 Ambientes configurados:")
    print("      • Local: backend/.env")
    print("      • Railway: backend/.env.railway (se existir)")
    
    # 4. Verificar se frontend tem node_modules
    print("\n📦 Verificando dependências do frontend...")
    frontend_node_modules = "frontend/node_modules"
    
    if not os.path.exists(frontend_node_modules):
        print("   ⚠️ node_modules não encontrado, será instalado no build")
    else:
        print("   ✅ node_modules encontrado")
    
    # 5. Mostrar comandos para rodar
    print("\n🚀 COMANDOS PARA RODAR LOCALMENTE:")
    print("-" * 80)
    print("1. Parar containers existentes:")
    print("   docker compose down")
    print()
    print("2. Construir e rodar todos os serviços:")
    print("   docker compose up --build")
    print()
    print("3. Rodar em background:")
    print("   docker compose up --build -d")
    print()
    print("4. Ver logs:")
    print("   docker compose logs -f")
    print()
    print("5. Parar tudo:")
    print("   docker compose down")
    print()
    print("📋 SERVIÇOS DISPONÍVEIS:")
    print("   • Frontend: http://localhost:80")
    print("   • Backend: http://localhost:8000")
    print("   • Database: localhost:5432")
    print("   • Redis: localhost:6379")
    print()
    print("🔧 PRÓXIMOS PASSOS:")
    print("   1. Rodar: docker compose up --build")
    print("   2. Aguardar todos os serviços subirem")
    print("   3. Acessar: http://localhost:80")
    print("   4. Testar sistema de notificações")
    
    return True

if __name__ == '__main__':
    setup_local_environment()
