# 🧩 ALREA SENSE

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-4.2+-green.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/react-18.2+-blue.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.2+-blue.svg)](https://www.typescriptlang.org/)

Plataforma SaaS multi-tenant para chat e atendimento de clientes em conversas do WhatsApp.

<!-- deploy trigger 2026-02-09 -->

## 🚀 Stack

- **Backend:** Django 5 + DRF + Channels + RabbitMQ (NÃO Celery)
- **Frontend:** React + TypeScript + Vite + Tailwind + shadcn/ui
- **Banco:** PostgreSQL + pgvector
- **Infra:** Docker + Railway
- **IA:** MCP (n8n HTTP) ou modelo local (Qwen/Ollama)
- **Billing:** Stripe
- **Realtime:** Django Channels

## 🏗️ Estrutura

```
/evosense
  /backend          # Django API
  /frontend         # React App
  /docs            # Documentação
  /scripts         # Scripts de setup
  docker-compose.yml
  README.md
```

## 🚀 Quick Start

### Opção 1: Setup Automático (Recomendado)

#### Linux/macOS
```bash
git clone <repo>
cd evosense
chmod +x scripts/setup.sh
./scripts/setup.sh
```

#### Windows
```powershell
git clone <repo>
cd evosense
.\scripts\setup.ps1
```

### Opção 2: Setup Manual

#### Pré-requisitos
- Docker e Docker Compose
- Node.js 18+ (para desenvolvimento frontend)
- Python 3.11+ (para desenvolvimento backend)

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
pip install -r requirements.txt
cp env.example .env
# Edite .env com suas configurações
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

#### Frontend
```bash
cd frontend
npm install
cp .env.example .env
# Edite .env com suas configurações
npm run dev
```

#### RabbitMQ Worker (terminal separado)
```bash
cd backend
python manage.py run_rabbitmq_worker
```

### Opção 3: Docker

```bash
docker-compose up --build
```

## 📚 Documentação

- **[📚 Documentação Consolidada](DOCUMENTACAO_CONSOLIDADA.md)** - Guia completo e atualizado
- **[🚦 Regras de Desenvolvimento](rules.md)** - Convenções e padrões do projeto
- **[⚡ Otimizações de Performance](OTIMIZACOES_PERFORMANCE_CHAT.md)** - Melhorias implementadas
- **[📡 WebSocket vs Webhooks](ANALISE_WEBSOCKET_EVOLUTION.md)** - Análise de integração

## 🎯 Features

- ✅ **Ingestão Evolution API** - WebSocket em tempo real
- ✅ **Análise de IA** - Sentiment, emotion, satisfaction, tone
- ✅ **Busca semântica** - pgvector para encontrar mensagens similares
- ✅ **Multi-tenancy** - Isolamento completo por tenant
- ✅ **Billing Stripe** - Planos e cobrança automática
- ✅ **Experimentos de prompt** - A/B testing de prompts de IA
- ✅ **WebSockets** - Updates em tempo real
- ✅ **Dashboard React** - Interface moderna e responsiva

## 🔧 Configuração

### Variáveis de Ambiente

#### Backend (.env)
```env
DJANGO_SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://host:port/0
STRIPE_SECRET_KEY=sk_test_...
N8N_AI_WEBHOOK=https://your-n8n-instance.com/webhook/ai-analysis
EVO_BASE_URL=https://your-evolution-api.com
```

#### Frontend (.env)
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

### Acesso Inicial

Após o setup, acesse:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Admin Django**: http://localhost:8000/admin

**Credenciais padrão:**
- Username: `admin`
- Password: `admin123`

## 🚀 Deploy em Produção

### Railway (Recomendado)
1. Conecte seu repositório ao Railway
2. Configure as variáveis de ambiente
3. Deploy automático no push

### Docker
```bash
docker-compose -f docker-compose.prod.yml up -d
```

Veja [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) para instruções detalhadas.

## 🧪 Desenvolvimento

### Estrutura do Backend
```
backend/
├── apps/
│   ├── tenancy/     # Multi-tenancy
│   ├── authn/       # Autenticação
│   ├── connections/ # Evolution API
│   ├── messages/    # Mensagens + pgvector
│   ├── ai/          # IA e embeddings
│   ├── experiments/ # Experimentos de prompt
│   ├── billing/     # Stripe integration
│   └── common/      # Utilitários
├── ingestion/       # Evolution WebSocket
└── management/      # Django commands
```

### Estrutura do Frontend
```
frontend/
├── src/
│   ├── components/  # Componentes React
│   ├── pages/       # Páginas da aplicação
│   ├── stores/      # Zustand stores
│   ├── hooks/       # Custom hooks
│   └── lib/         # Utilitários
└── public/
```

### Comandos Úteis

```bash
# Backend
python manage.py migrate
python manage.py seed_data
python manage.py start_ingestion
python manage.py shell

# Frontend
npm run dev
npm run build
npm run preview

# Docker
docker-compose up --build
docker-compose logs -f
docker-compose down
```

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para detalhes.

## 🆘 Suporte

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Documentação**: [docs/](docs/)
- **Email**: support@evosense.com

## 🗺️ Roadmap

- [ ] Mobile app (React Native)
- [ ] API webhooks
- [ ] Relatórios avançados
- [ ] Integração com outros canais
- [ ] White-label solution
