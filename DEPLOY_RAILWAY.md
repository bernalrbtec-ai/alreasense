# 🚀 Deploy na Railway - Alrea Sense

Guia completo para fazer deploy do Alrea Sense na Railway.

## 📋 Pré-requisitos

1. Conta na Railway (https://railway.app)
2. Repositório Git (GitHub, GitLab ou Bitbucket)
3. Railway CLI instalado (opcional, mas recomendado)

## 🔧 Passo 1: Preparar o Repositório

### 1.1 Criar arquivo `.railwayignore` (opcional)

```
node_modules/
__pycache__/
*.pyc
.env
.env.local
*.log
.DS_Store
.vscode/
.idea/
```

### 1.2 Commitar as mudanças

```bash
git add .
git commit -m "chore: prepare for Railway deployment"
git push origin main
```

## 🌐 Passo 2: Criar Projeto na Railway

1. Acesse https://railway.app
2. Clique em **"New Project"**
3. Selecione **"Deploy from GitHub repo"**
4. Autorize a Railway a acessar seu repositório
5. Selecione o repositório **Alrea Sense**

## 🗄️ Passo 3: Adicionar Serviços

### 3.1 PostgreSQL

1. No projeto, clique em **"+ New"**
2. Selecione **"Database" → "PostgreSQL"**
3. Anote as credenciais geradas automaticamente

### 3.2 Redis

1. Clique em **"+ New"**
2. Selecione **"Database" → "Redis"**
3. Anote a URL de conexão gerada

## ⚙️ Passo 4: Configurar Variáveis de Ambiente

### 4.1 Backend (Django)

No serviço do backend, adicione as seguintes variáveis:

```bash
# Django
DJANGO_SECRET_KEY=<gerar_uma_chave_secreta_aleatoria>
DEBUG=False
ALLOWED_HOSTS=.railway.app,localhost,127.0.0.1
DJANGO_SETTINGS_MODULE=alrea_sense.settings

# Database (copiar da Railway)
DATABASE_URL=postgresql://user:password@host:port/dbname

# Redis (copiar da Railway)
REDIS_URL=redis://default:password@host:port

# Celery
CELERY_BROKER_URL=$REDIS_URL
CELERY_RESULT_BACKEND=$REDIS_URL

# CORS (adicionar domínio do frontend)
CORS_ALLOWED_ORIGINS=https://seu-frontend.railway.app

# Stripe (se já tiver conta)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...

# Evolution API (configurar depois)
EVOLUTION_API_URL=https://seu-evolution-api.com
EVOLUTION_API_KEY=sua_api_key

# Logs
LOG_LEVEL=INFO
```

### 4.2 Frontend (React/Vite)

No serviço do frontend, adicione:

```bash
VITE_API_BASE_URL=https://seu-backend.railway.app
VITE_WS_BASE_URL=wss://seu-backend.railway.app
```

## 📦 Passo 5: Configurar Build Commands

### 5.1 Backend

**Build Command:**
```bash
cd backend && pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

**Start Command:**
```bash
cd backend && daphne -b 0.0.0.0 -p $PORT alrea_sense.asgi:application
```

### 5.2 Frontend

**Build Command:**
```bash
cd frontend && npm install && npm run build
```

**Start Command:**
```bash
cd frontend && npm run preview -- --host 0.0.0.0 --port $PORT
```

## 🔄 Passo 6: Adicionar Workers Celery

### 6.1 Celery Worker

1. Clique em **"+ New" → "Empty Service"**
2. Conecte ao mesmo repositório
3. Configure:

**Start Command:**
```bash
cd backend && celery -A alrea_sense worker -l info
```

**Variáveis de Ambiente:** (mesmas do backend)

### 6.2 Celery Beat

1. Clique em **"+ New" → "Empty Service"**
2. Conecte ao mesmo repositório
3. Configure:

**Start Command:**
```bash
cd backend && celery -A alrea_sense beat -l info
```

**Variáveis de Ambiente:** (mesmas do backend)

## 🔐 Passo 7: Criar Superusuário

Após o deploy, execute via Railway CLI:

```bash
railway run python backend/manage.py createsuperuser
```

Ou via Railway Dashboard:
1. Acesse o serviço do backend
2. Vá em **"Settings" → "Shell"**
3. Execute:
```bash
cd backend
python manage.py shell
```

```python
from apps.authn.models import User
from apps.tenancy.models import Tenant

tenant = Tenant.objects.create(name='Admin Tenant')
user = User.objects.create_superuser(
    username='admin',
    email='admin@example.com',
    password='senha_segura_aqui',
    tenant=tenant
)
print(f'Superuser created: {user.username}')
```

## 🌐 Passo 8: Configurar Domínios Customizados (Opcional)

### 8.1 Backend
1. No serviço do backend, vá em **"Settings" → "Domains"**
2. Adicione um domínio customizado (ex: `api.alreasense.com`)

### 8.2 Frontend
1. No serviço do frontend, vá em **"Settings" → "Domains"**
2. Adicione um domínio customizado (ex: `app.alreasense.com`)

### 8.3 Atualizar CORS e URLs
Após adicionar domínios customizados, atualize:
- `ALLOWED_HOSTS` no backend
- `CORS_ALLOWED_ORIGINS` no backend
- `VITE_API_BASE_URL` e `VITE_WS_BASE_URL` no frontend

## 📊 Passo 9: Monitoramento

### 9.1 Logs
- Acesse cada serviço e vá em **"Deployments" → "View Logs"**

### 9.2 Métricas
- Monitore CPU, RAM e Network em **"Metrics"**

### 9.3 Health Checks
- Configure health checks em **"Settings" → "Health Check"**
- Endpoint: `/health/`
- Intervalo: 30 segundos

## 🔧 Passo 10: Troubleshooting

### Erro: "Module not found"
- Verifique se o `requirements.txt` ou `package.json` está correto
- Rode o build novamente

### Erro: "Database connection failed"
- Verifique a `DATABASE_URL`
- Certifique-se que o PostgreSQL está rodando

### Erro: "Static files not found"
- Execute `python manage.py collectstatic --noinput`
- Verifique `STATIC_ROOT` e `STATIC_URL`

### Frontend não conecta ao Backend
- Verifique `VITE_API_BASE_URL`
- Verifique `CORS_ALLOWED_ORIGINS` no backend
- Use HTTPS em produção

## 📝 Checklist Final

- [ ] PostgreSQL configurado e rodando
- [ ] Redis configurado e rodando
- [ ] Backend rodando com migrações aplicadas
- [ ] Frontend rodando e conectando ao backend
- [ ] Celery Worker rodando
- [ ] Celery Beat rodando
- [ ] Superusuário criado
- [ ] CORS configurado corretamente
- [ ] HTTPS habilitado
- [ ] Domínios customizados configurados (opcional)
- [ ] Health checks configurados
- [ ] Logs sendo monitorados

## 🎯 URLs Finais

Após o deploy, você terá:

- **Frontend:** `https://seu-projeto-frontend.railway.app`
- **Backend API:** `https://seu-projeto-backend.railway.app`
- **Admin Django:** `https://seu-projeto-backend.railway.app/admin/`
- **API Docs:** `https://seu-projeto-backend.railway.app/api/`

## 💰 Custos Estimados (Railway)

- **Hobby Plan:** $5/mês por serviço
- **Estimativa Total:** ~$30-40/mês (Backend + Frontend + PostgreSQL + Redis + 2 Workers)
- **Trial:** $5 de crédito gratuito para testar

## 🚀 Deploy Rápido (Railway CLI)

Se preferir usar a CLI:

```bash
# Instalar Railway CLI
npm i -g @railway/cli

# Login
railway login

# Criar projeto
railway init

# Adicionar PostgreSQL
railway add --plugin postgresql

# Adicionar Redis
railway add --plugin redis

# Deploy
railway up

# Ver logs
railway logs
```

## 📚 Recursos Úteis

- [Railway Docs](https://docs.railway.app/)
- [Railway Discord](https://discord.gg/railway)
- [Railway Status](https://status.railway.app/)

---

**Boa sorte com o deploy! 🚀**

Se encontrar problemas, verifique os logs e a documentação da Railway.

