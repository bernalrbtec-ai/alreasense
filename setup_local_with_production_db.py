#!/usr/bin/env python
"""
Script para configurar ambiente local usando banco de produção
"""
import os
import shutil
import subprocess
import sys

def create_production_db_env():
    print("="*80)
    print("CONFIGURANDO AMBIENTE LOCAL COM BANCO DE PRODUCAO")
    print("="*80)
    
    # 1. Backup do .env atual
    env_local = "backend/.env"
    env_backup = "backend/.env.backup"
    
    if os.path.exists(env_local):
        shutil.copy2(env_local, env_backup)
        print(f"Backup criado: {env_backup}")
    
    # 2. Criar novo .env com banco de produção
    env_content = """# Django Settings - Local com DB de Produção
SECRET_KEY=N;.!iB5@sw?D2wJPr{Ysmt5][R%5.aHyAuvNpM_@DOb:OX*<.f
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,alreasense-backend-production.up.railway.app

# Database - PostgreSQL de Produção (Railway)
DATABASE_URL=postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway

# Redis - Local (Docker)
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CHANNELS_REDIS_URL=redis://redis:6379/1

# CORS - Local
CORS_ALLOWED_ORIGINS=http://localhost,http://localhost:5173,http://127.0.0.1,http://127.0.0.1:5173,https://alreasense-production.up.railway.app

# CSRF - Local
CSRF_TRUSTED_ORIGINS=http://localhost,http://localhost:5173,http://127.0.0.1,http://127.0.0.1:5173,https://alreasense-production.up.railway.app

# Email - Console para desenvolvimento
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Evolution API (configurar depois)
EVO_BASE_URL=http://localhost:8080
EVO_API_KEY=test-key
"""
    
    with open(env_local, 'w') as f:
        f.write(env_content)
    
    print(f"✅ Arquivo {env_local} configurado para usar banco de produção")
    
    # 3. Atualizar docker-compose para não usar banco local
    print("\n🐳 Configurando Docker Compose...")
    
    # Ler docker-compose.yml
    with open('docker-compose.yml', 'r') as f:
        compose_content = f.read()
    
    # Criar versão sem banco local
    compose_without_db = compose_content.replace(
        'depends_on:\n      db:\n        condition: service_healthy\n      redis:',
        'depends_on:\n      redis:'
    ).replace(
        'DATABASE_URL=postgresql://postgres:postgres@db:5432/alrea_sense',
        'DATABASE_URL=postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway'
    )
    
    # Salvar versão modificada
    with open('docker-compose.prod-db.yml', 'w') as f:
        f.write(compose_without_db)
    
    print("✅ Docker Compose configurado: docker-compose.prod-db.yml")
    
    # 4. Mostrar instruções
    print("\n" + "="*80)
    print("🎉 CONFIGURAÇÃO CONCLUÍDA!")
    print("="*80)
    print("📋 CONFIGURAÇÃO ATUAL:")
    print("   • Backend: Local (Docker)")
    print("   • Frontend: Local (Docker)")
    print("   • Database: Produção (Railway)")
    print("   • Redis: Local (Docker)")
    print("   • Celery: Local (Docker)")
    print()
    print("🚀 COMANDOS PARA RODAR:")
    print("   1. Parar containers existentes:")
    print("      docker compose down")
    print()
    print("   2. Rodar apenas backend, frontend e Redis:")
    print("      docker compose -f docker-compose.prod-db.yml up --build")
    print()
    print("   3. Ou usar o script:")
    print("      python dev.py start-prod-db")
    print()
    print("📋 URLs:")
    print("   • Frontend: http://localhost:80")
    print("   • Backend: http://localhost:8000")
    print("   • Admin: http://localhost:8000/admin/")
    print()
    print("👤 LOGIN:")
    print("   • Use os usuários existentes no banco de produção")
    print("   • Ex: paulo.bernal@alrea.ai")
    print()
    print("⚠️ IMPORTANTE:")
    print("   • Você estará usando dados REAIS de produção")
    print("   • Tenha cuidado com modificações")
    print("   • Para voltar ao banco local: python restore_local_db.py")
    
    return True

def restore_local_db():
    print("="*80)
    print("🔄 RESTAURANDO CONFIGURAÇÃO LOCAL")
    print("="*80)
    
    env_local = "backend/.env"
    env_backup = "backend/.env.backup"
    
    if os.path.exists(env_backup):
        shutil.copy2(env_backup, env_local)
        print(f"✅ Arquivo {env_local} restaurado do backup")
    else:
        print("❌ Backup não encontrado")
        return False
    
    print("✅ Configuração local restaurada!")
    print("📋 Para usar banco local:")
    print("   docker compose up --build")
    
    return True

def main():
    if len(sys.argv) < 2:
        print("Uso: python setup_local_with_production_db.py [comando]")
        print("Comandos:")
        print("  setup    - Configurar local com banco de produção")
        print("  restore  - Restaurar configuração local")
        return
    
    command = sys.argv[1].lower()
    
    if command == "setup":
        create_production_db_env()
    elif command == "restore":
        restore_local_db()
    else:
        print(f"❌ Comando desconhecido: {command}")

if __name__ == '__main__':
    main()
