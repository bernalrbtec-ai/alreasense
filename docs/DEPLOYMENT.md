# 🚀 EvoSense - Deployment Guide

## Visão Geral

Este guia cobre o deployment do EvoSense em diferentes ambientes, com foco no Railway (recomendado) e Docker local.

## 🚂 Railway Deployment (Recomendado)

### 1. Preparação

#### Conta Railway
1. Acesse [railway.app](https://railway.app)
2. Crie uma conta ou faça login
3. Conecte sua conta GitHub

#### Repositório
1. Faça fork do repositório EvoSense
2. Conecte o repositório ao Railway

### 2. Configuração dos Serviços

#### PostgreSQL Database
```bash
# No Railway Dashboard:
1. New Project → Add Database → PostgreSQL
2. Aguarde a criação do banco
3. Copie a DATABASE_URL gerada
```

**Configuração inicial do banco:**
```sql
-- Conectar ao banco e executar:
CREATE EXTENSION IF NOT EXISTS vector;
```

#### Redis
```bash
# No Railway Dashboard:
1. Add Service → Redis
2. Copie a REDIS_URL gerada
```

#### Backend Service
```bash
# No Railway Dashboard:
1. Add Service → GitHub Repo → Selecione o repositório
2. Root Directory: /backend
3. Build Command: pip install -r requirements.txt
4. Start Command: python manage.py migrate && daphne -b 0.0.0.0 -p $PORT evosense.asgi:application
```

**Variáveis de ambiente:**
```env
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-app.railway.app
DATABASE_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://host:port/0
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
N8N_AI_WEBHOOK=https://your-n8n-instance.com/webhook/ai-analysis
AI_MODEL_NAME=qwen-local
AI_EMBEDDING_MODEL=qwen-mini-embeddings
EVO_BASE_URL=https://your-evolution-api.com
EVO_API_KEY=your-evolution-api-key
CORS_ALLOWED_ORIGINS=https://your-frontend.railway.app
CSRF_TRUSTED_ORIGINS=https://your-frontend.railway.app
```

#### Frontend Service
```bash
# No Railway Dashboard:
1. Add Service → GitHub Repo → Selecione o repositório
2. Root Directory: /frontend
3. Build Command: npm ci && npm run build
4. Start Command: npm run preview -- --host 0.0.0.0 --port $PORT
```

**Variáveis de ambiente:**
```env
VITE_API_BASE_URL=https://your-backend.railway.app
VITE_WS_BASE_URL=wss://your-backend.railway.app
```

#### Celery Worker
```bash
# No Railway Dashboard:
1. Add Service → GitHub Repo → Selecione o repositório
2. Root Directory: /backend
3. Build Command: pip install -r requirements.txt
4. Start Command: celery -A evosense worker -l info
```

#### Celery Beat (Opcional)
```bash
# Para tarefas agendadas:
1. Add Service → GitHub Repo → Selecione o repositório
2. Root Directory: /backend
3. Build Command: pip install -r requirements.txt
4. Start Command: celery -A evosense beat -l info
```

### 3. Configuração de Domínio

#### Custom Domain (Opcional)
1. No Railway Dashboard → Settings → Domains
2. Adicione seu domínio personalizado
3. Configure DNS conforme instruções

### 4. Deploy

```bash
# Push para o repositório conectado:
git add .
git commit -m "Deploy to Railway"
git push origin main

# Railway fará o deploy automaticamente
```

## 🐳 Docker Local

### 1. Pré-requisitos
```bash
# Instalar Docker e Docker Compose
# Ubuntu/Debian:
sudo apt update
sudo apt install docker.io docker-compose

# macOS:
brew install docker docker-compose

# Windows:
# Instalar Docker Desktop
```

### 2. Configuração

#### Clone do repositório
```bash
git clone <repository-url>
cd evosense
```

#### Variáveis de ambiente
```bash
# Copiar arquivo de exemplo
cp backend/env.example backend/.env

# Editar .env com suas configurações
nano backend/.env
```

**Configuração mínima:**
```env
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://postgres:postgres@db:5432/evosense
REDIS_URL=redis://redis:6379/0
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
N8N_AI_WEBHOOK=https://your-n8n-instance.com/webhook/ai-analysis
```

### 3. Execução

```bash
# Build e start dos serviços
docker-compose up --build

# Em background
docker-compose up -d --build

# Ver logs
docker-compose logs -f

# Parar serviços
docker-compose down
```

### 4. Acessos

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Admin Django**: http://localhost:8000/admin
- **Health Check**: http://localhost:8000/health

## 🔧 Configuração Avançada

### 1. SSL/HTTPS

#### Railway (Automático)
- Railway fornece SSL automaticamente
- Certificados Let's Encrypt gerenciados

#### Docker Local (Nginx Proxy)
```yaml
# docker-compose.override.yml
version: "3.9"
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
      - frontend
```

### 2. Backup Automático

#### Railway
```bash
# Backup automático habilitado por padrão
# Acesse Railway Dashboard → Database → Backups
```

#### Docker Local
```bash
# Script de backup
#!/bin/bash
docker-compose exec db pg_dump -U postgres evosense > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 3. Monitoramento

#### Health Checks
```bash
# Backend health
curl http://localhost:8000/health

# Database connection
docker-compose exec backend python manage.py check --database default

# Redis connection
docker-compose exec redis redis-cli ping
```

#### Logs
```bash
# Railway
# Acesse Railway Dashboard → Service → Logs

# Docker
docker-compose logs -f backend
docker-compose logs -f celery
```

## 🔐 Segurança

### 1. Variáveis de Ambiente

#### Produção
```env
# NUNCA commitar no Git
DJANGO_SECRET_KEY=generate-strong-secret-key
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
EVO_API_KEY=your-secure-api-key
```

#### Geração de Secret Key
```python
# Python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### 2. Firewall

#### Railway
- Firewall automático configurado
- Apenas portas necessárias expostas

#### Docker Local
```bash
# UFW (Ubuntu)
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

### 3. Rate Limiting

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}
```

## 📊 Monitoramento e Alertas

### 1. Métricas Básicas

#### Railway
- CPU, Memory, Network usage
- Request count e response time
- Error rate

#### Custom Metrics
```python
# apps/common/metrics.py
from django.core.cache import cache
from django.db.models import Count

def get_tenant_metrics(tenant_id):
    return {
        'messages_count': Message.objects.filter(tenant_id=tenant_id).count(),
        'active_connections': EvolutionConnection.objects.filter(
            tenant_id=tenant_id, is_active=True
        ).count(),
        'avg_sentiment': Message.objects.filter(
            tenant_id=tenant_id, sentiment__isnull=False
        ).aggregate(avg=Avg('sentiment'))['avg']
    }
```

### 2. Alertas

#### Railway
- Configurar alertas no Dashboard
- Email/Slack notifications

#### Custom Alerts
```python
# apps/common/alerts.py
import requests

def send_alert(message, severity='warning'):
    webhook_url = settings.ALERT_WEBHOOK_URL
    payload = {
        'text': f'[{severity.upper()}] EvoSense: {message}',
        'channel': '#alerts'
    }
    requests.post(webhook_url, json=payload)
```

## 🔄 CI/CD

### 1. GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to Railway

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Tests
        run: |
          cd backend
          pip install -r requirements.txt
          python manage.py test
      
      - name: Deploy to Railway
        uses: railway-app/railway-deploy@v1
        with:
          railway-token: ${{ secrets.RAILWAY_TOKEN }}
```

### 2. Railway Auto-Deploy

```bash
# Configurar no Railway Dashboard:
# Settings → Source → Auto Deploy: ON
# Branch: main
```

## 🚨 Troubleshooting

### 1. Problemas Comuns

#### Database Connection
```bash
# Verificar conexão
docker-compose exec backend python manage.py dbshell

# Reset migrations
docker-compose exec backend python manage.py migrate --fake-initial
```

#### Redis Connection
```bash
# Testar Redis
docker-compose exec redis redis-cli ping

# Limpar cache
docker-compose exec redis redis-cli flushall
```

#### WebSocket Issues
```bash
# Verificar Channels
docker-compose exec backend python manage.py shell
>>> from channels.layers import get_channel_layer
>>> layer = get_channel_layer()
>>> layer.group_send("test", {"type": "test"})
```

### 2. Logs Úteis

```bash
# Django logs
docker-compose logs backend | grep ERROR

# Celery logs
docker-compose logs celery | grep ERROR

# Database logs
docker-compose logs db | grep ERROR
```

### 3. Performance Issues

#### Database
```sql
-- Verificar queries lentas
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Verificar índices
SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes;
```

#### pgvector
```sql
-- Verificar performance do índice vetorial
SELECT * FROM pg_stat_user_indexes 
WHERE indexname = 'idx_message_embedding';

-- Reindexar se necessário
REINDEX INDEX idx_message_embedding;
```

## 📈 Scaling

### 1. Horizontal Scaling

#### Railway
- Auto-scaling baseado em CPU/Memory
- Load balancer automático

#### Docker
```yaml
# docker-compose.scale.yml
version: "3.9"
services:
  backend:
    deploy:
      replicas: 3
  
  celery:
    deploy:
      replicas: 2
```

### 2. Database Scaling

#### Read Replicas
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'evosense',
        'HOST': 'primary-db.railway.app',
    },
    'read_replica': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'evosense',
        'HOST': 'replica-db.railway.app',
    }
}
```

### 3. Cache Scaling

#### Redis Cluster
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://cluster.railway.app:6379/0',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

## 📋 Checklist de Deploy

### Pré-Deploy
- [ ] Variáveis de ambiente configuradas
- [ ] Secrets não commitados
- [ ] Testes passando
- [ ] Migrations aplicadas
- [ ] Backup do banco atual

### Deploy
- [ ] Serviços criados no Railway
- [ ] Domínios configurados
- [ ] SSL funcionando
- [ ] Health checks passando

### Pós-Deploy
- [ ] Funcionalidades testadas
- [ ] Monitoramento ativo
- [ ] Alertas configurados
- [ ] Backup automático funcionando
- [ ] Documentação atualizada

## 🆘 Suporte

### Recursos
- [Railway Docs](https://docs.railway.app)
- [Django Deployment](https://docs.djangoproject.com/en/stable/howto/deployment/)
- [Docker Compose](https://docs.docker.com/compose/)

### Contato
- Issues: GitHub Issues
- Email: support@evosense.com
- Discord: EvoSense Community
