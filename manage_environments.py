#!/usr/bin/env python
"""
Script para gerenciar ambientes (local vs Railway)
"""
import os
import shutil
import sys

def show_help():
    print("="*80)
    print("🔧 GERENCIADOR DE AMBIENTES")
    print("="*80)
    print("Uso: python manage_environments.py [comando]")
    print()
    print("Comandos disponíveis:")
    print("  local     - Configurar para ambiente local")
    print("  railway   - Configurar para ambiente Railway")
    print("  status    - Mostrar status atual")
    print("  help      - Mostrar esta ajuda")
    print()
    print("Exemplos:")
    print("  python manage_environments.py local")
    print("  python manage_environments.py railway")
    print("  python manage_environments.py status")

def show_status():
    print("="*80)
    print("📊 STATUS DOS AMBIENTES")
    print("="*80)
    
    env_local = "backend/.env"
    env_railway = "backend/.env.railway"
    
    print(f"📁 Arquivo local: {env_local}")
    if os.path.exists(env_local):
        print("   ✅ Existe")
        with open(env_local, 'r') as f:
            content = f.read()
            if "localhost" in content:
                print("   🏠 Configurado para LOCAL")
            else:
                print("   ☁️ Configurado para RAILWAY")
    else:
        print("   ❌ Não existe")
    
    print(f"\n📁 Arquivo Railway: {env_railway}")
    if os.path.exists(env_railway):
        print("   ✅ Existe")
    else:
        print("   ❌ Não existe")
    
    print(f"\n📋 Docker Compose:")
    if os.path.exists("docker-compose.yml"):
        print("   ✅ Configurado")
    else:
        print("   ❌ Não encontrado")

def setup_local():
    print("="*80)
    print("🏠 CONFIGURANDO PARA AMBIENTE LOCAL")
    print("="*80)
    
    env_local = "backend/.env"
    
    if not os.path.exists(env_local):
        print("❌ Arquivo backend/.env não encontrado")
        return False
    
    # Verificar se já está configurado para local
    with open(env_local, 'r') as f:
        content = f.read()
        if "localhost" in content and "db:5432" in content:
            print("✅ Já está configurado para ambiente local")
            return True
    
    print("⚠️ Arquivo .env não está configurado para local")
    print("📝 Edite manualmente o arquivo backend/.env para:")
    print("   • DATABASE_URL=postgresql://postgres:postgres@db:5432/alrea_sense")
    print("   • CORS_ALLOWED_ORIGINS=http://localhost,http://localhost:5173,http://127.0.0.1,http://127.0.0.1:5173")
    print("   • DEBUG=True")
    
    return True

def setup_railway():
    print("="*80)
    print("☁️ CONFIGURANDO PARA AMBIENTE RAILWAY")
    print("="*80)
    
    print("⚠️ Para Railway, configure as variáveis de ambiente diretamente no dashboard:")
    print("   • SECRET_KEY")
    print("   • DATABASE_URL")
    print("   • REDIS_URL")
    print("   • CORS_ALLOWED_ORIGINS")
    print("   • DEBUG=False")
    print()
    print("📋 Ou use o arquivo backend/.env.railway como referência")
    
    return True

def main():
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "help":
        show_help()
    elif command == "status":
        show_status()
    elif command == "local":
        setup_local()
    elif command == "railway":
        setup_railway()
    else:
        print(f"❌ Comando desconhecido: {command}")
        show_help()

if __name__ == '__main__':
    main()
