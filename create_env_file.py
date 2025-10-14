#!/usr/bin/env python
"""
Criar arquivo .env com encoding correto
"""
import os

def create_env_file():
    env_content = """# Django Settings - Local com DB de Producao
SECRET_KEY=N;.!iB5@sw?D2wJPr{Ysmt5][R%5.aHyAuvNpM_@DOb:OX*<.f
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,alreasense-backend-production.up.railway.app

# Database - PostgreSQL de Producao (Railway)
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
    
    with open('backend/.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("Arquivo backend/.env criado com sucesso!")
    print("Configurado para usar banco de producao do Railway")

if __name__ == '__main__':
    create_env_file()
