# 🏗️ EvoSense - Arquitetura

## Visão Geral

O EvoSense é uma plataforma SaaS multi-tenant para análise de sentimento e satisfação de clientes em conversas do WhatsApp, construída com Django + React + PostgreSQL + pgvector.

## Arquitetura do Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   React + Vite  │◄──►│   Django + DRF  │◄──►│   PostgreSQL    │
│   Tailwind UI   │    │   Channels      │    │   + pgvector    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WebSocket     │    │   Celery        │    │   Redis         │
│   Real-time     │    │   Background    │    │   Cache + Queue │
│   Updates       │    │   Tasks         │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Evolution API │
                       │   WhatsApp      │
                       │   WebSocket     │
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   AI Service    │
                       │   N8N / Local   │
                       │   Qwen/Ollama   │
                       └─────────────────┘
```

## Componentes Principais

### 1. Frontend (React + Vite)
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS + shadcn/ui
- **State Management**: Zustand
- **Routing**: React Router
- **HTTP Client**: Axios
- **WebSocket**: Native WebSocket API

### 2. Backend (Django)
- **Framework**: Django 5.0 + Django REST Framework
- **WebSockets**: Django Channels + Redis
- **Background Tasks**: Celery + Redis
- **Authentication**: JWT (Simple JWT)
- **Database**: PostgreSQL + pgvector
- **Multi-tenancy**: Row-level isolation

### 3. Database (PostgreSQL + pgvector)
- **Primary DB**: PostgreSQL 15+
- **Vector Search**: pgvector extension
- **Embeddings**: 768-dimensional vectors
- **Indexing**: IVFFLAT for similarity search

### 4. Message Queue (Redis)
- **Cache**: Redis 7
- **Celery Broker**: Redis
- **WebSocket Layer**: Redis Channel Layer

### 5. AI Integration
- **Primary**: N8N webhook (HTTP)
- **Fallback**: Local Qwen/Ollama models
- **Embeddings**: Qwen-mini-embeddings
- **Analysis**: Sentiment, emotion, satisfaction, tone

### 6. WhatsApp Integration
- **API**: Evolution API
- **Protocol**: WebSocket
- **Ingestion**: Python asyncio client
- **Real-time**: Message streaming

## Fluxo de Dados

### 1. Ingestão de Mensagens
```
Evolution API → WebSocket → Django → Message Model → Celery Task → AI Analysis
```

### 2. Análise de IA
```
Message → AI Service → Sentiment Analysis → Embedding Generation → Database Storage
```

### 3. Busca Semântica
```
User Query → Embedding → pgvector Search → Similar Messages → Results
```

### 4. Real-time Updates
```
AI Analysis → WebSocket → Frontend → UI Update
```

## Multi-tenancy

### Estratégia
- **Row-level isolation**: Cada modelo tem `tenant_id`
- **User isolation**: Usuários pertencem a um tenant
- **Permission filtering**: Todas as queries filtram por tenant
- **WebSocket segregation**: Conexões isoladas por tenant

### Implementação
```python
# Exemplo de filtro automático
class TenantFilterBackend(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        return queryset.filter(tenant=request.user.tenant)
```

## Segurança

### Autenticação
- **JWT Tokens**: Access + Refresh tokens
- **Token Storage**: HTTP-only cookies (recomendado)
- **Token Rotation**: Refresh token rotation

### Autorização
- **Role-based**: Admin vs Operator
- **Tenant isolation**: Acesso apenas aos dados do tenant
- **API permissions**: DRF permission classes

### Dados Sensíveis
- **PII Sanitization**: Regex para CPF, email, cartão
- **Token Encryption**: Evolution tokens criptografados
- **Log Sanitization**: Logs não contêm dados sensíveis

## Escalabilidade

### Horizontal Scaling
- **Stateless Backend**: Django stateless
- **Database**: PostgreSQL com read replicas
- **Cache**: Redis Cluster
- **Load Balancer**: Nginx/HAProxy

### Vertical Scaling
- **Database**: Connection pooling
- **Celery**: Multiple workers
- **WebSocket**: Redis pub/sub scaling

## Monitoramento

### Logs
- **Structured Logging**: JSON format
- **Request Tracking**: Request ID correlation
- **Tenant Context**: Tenant ID em todos os logs

### Métricas
- **Application**: Custom metrics via Django
- **Database**: PostgreSQL stats
- **Infrastructure**: System metrics

### Health Checks
- **Backend**: `/health/` endpoint
- **Database**: Connection check
- **Redis**: Ping check
- **WebSocket**: Ping/pong

## Deploy

### Railway (Recomendado)
- **Services**: Backend, Frontend, Database, Redis
- **Environment**: Production-ready
- **Scaling**: Auto-scaling disponível

### Docker
- **Multi-stage builds**: Otimizado para produção
- **Health checks**: Container health monitoring
- **Volume mounts**: Persistent data

### CI/CD
- **GitHub Actions**: Automated testing
- **Railway**: Auto-deploy on push
- **Environment**: Staging + Production

## Performance

### Otimizações
- **Database**: Proper indexing, query optimization
- **Cache**: Redis caching strategy
- **Frontend**: Code splitting, lazy loading
- **API**: Pagination, filtering

### pgvector Performance
- **Index Type**: IVFFLAT
- **Lists**: 100 (ajustável)
- **Dimensions**: 768 (Qwen embeddings)
- **Similarity**: Cosine distance

## Backup e Recovery

### Database
- **Automated Backups**: Daily backups
- **Point-in-time Recovery**: WAL archiving
- **Cross-region**: Backup replication

### Application Data
- **File Storage**: S3-compatible storage
- **Configuration**: Environment variables
- **Secrets**: Encrypted storage

## Desenvolvimento

### Local Setup
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Frontend
cd frontend
npm install
npm run dev

# Celery
celery -A evosense worker -l info
```

### Testing
- **Backend**: pytest + Django test client
- **Frontend**: Jest + React Testing Library
- **Integration**: API + WebSocket tests
- **E2E**: Playwright (opcional)

## Roadmap

### Fase 1 (Atual)
- ✅ Core functionality
- ✅ Multi-tenancy
- ✅ AI integration
- ✅ Real-time updates

### Fase 2
- 🔄 Advanced analytics
- 🔄 Custom dashboards
- 🔄 API webhooks
- 🔄 Mobile app

### Fase 3
- 📋 Multi-language support
- 📋 Advanced AI models
- 📋 Enterprise features
- 📋 White-label solution
