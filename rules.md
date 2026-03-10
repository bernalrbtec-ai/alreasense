# 🚦 ALREA SENSE — REGRAS DE DESENVOLVIMENTO

> **Versão:** 2.0  
> **Data:** 20 de Outubro de 2025  
> **Status:** ✅ Atualizado com arquitetura atual  

---

## 🎯 VISÃO GERAL

**ALREA Sense** é uma **plataforma SaaS multi-tenant** que integra múltiplos produtos:

### Produtos Ativos

1. **Flow** - Sistema de Campanhas WhatsApp
2. **Chat** - Atendimento completo: Chat, Respostas rápidas, Agenda, Contatos e Instâncias WhatsApp (limites de instâncias e usuários)
3. **Sense** - Análise de Sentimento com IA (legado)
4. **Notifications** - Notificações do Sistema
5. **API Pública** - Integração externa

### Stack Tecnológico ATUAL

```yaml
Backend:
  Framework: Django 5.0+
  API: Django REST Framework 3.14+
  WebSockets: Django Channels 4.0+ (com Redis)
  Async Tasks: RabbitMQ + aio-pika (NÃO usa Celery*)
  Database: PostgreSQL 15+ (com pgvector)
  Cache: Redis 7+
  Storage: MinIO/S3 (Railway)
  
Frontend:
  Framework: React 18+
  Language: TypeScript 5+
  Build: Vite 4.5+
  Styling: Tailwind CSS 3+
  Components: shadcn/ui + Lucide Icons
  State: Zustand 4+
  HTTP: Axios
  Forms: Validação manual (sem libraries)

Infrastructure:
  Deploy: Railway (PostgreSQL, Redis, MinIO, RabbitMQ)
  WebSockets: Daphne (ASGI server)
  Containers: Docker (apenas local)
  
Integrations:
  WhatsApp: Evolution API (WebSocket + HTTP)
  Billing: Stripe
  Auth: JWT (Simple JWT)
  IA: N8N webhook + Qwen/Ollama (legado Sense)
```

**⚠️ IMPORTANTE: O projeto NÃO USA CELERY!**
- ❌ Celery foi REMOVIDO do projeto
- ✅ Usa **RabbitMQ + aio-pika** para tarefas assíncronas
- ✅ Consumers RabbitMQ rodam via threads no `asgi.py`
- 🔴 Procfile ainda menciona Celery mas é **LEGADO** (não é usado)

---

## 🏗️ ARQUITETURA

### Estrutura de Diretórios

```
/Sense
  /backend
    manage.py
    /alrea_sense
      settings.py
      asgi.py          # ← Inicia RabbitMQ consumers aqui
      urls.py
      wsgi.py
    /apps
      /tenancy         # Multi-tenancy
      /authn           # Autenticação + usuários
      /connections     # Evolution API webhooks
      /notifications   # Notificações sistema
      /billing         # Stripe + planos
      /contacts        # Gestão de contatos
      /campaigns       # Sistema de campanhas
      /chat            # Flow Chat (tempo real)
      /chat_messages   # WebSocket chat messages (legado Sense)
      /ai              # IA + embeddings (legado Sense)
      /experiments     # A/B testing prompts (legado Sense)
      /common          # Middleware + utils
    /media             # Uploads temporários
    requirements.txt
    Dockerfile
  
  /frontend
    /src
      /components    # Componentes globais
      /modules       # Módulos por produto
        /chat
        /campaigns
        /contacts
      /pages         # Páginas principais
      /stores        # Zustand stores
      /hooks         # Custom hooks
      /lib           # Utilitários
    package.json
    vite.config.ts
    Dockerfile.frontend
  
  /docs              # Documentação técnica
  /scripts           # Scripts utilitários
  docker-compose.yml
  Procfile           # Railway deploy (LEGADO - não usa Celery)
  README.md
  rules.md           # ← ESTE ARQUIVO
```

---

## 🔄 PROCESSAMENTO ASSÍNCRONO

### ⚠️ ATENÇÃO: NÃO USAMOS CELERY!

**Arquitetura Atual:**

```
┌─────────────────────────────────────────────────────┐
│              PROCESSAMENTO ASSÍNCRONO                │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ✅ RabbitMQ (Broker):   amqp://railway.internal   │
│  ✅ aio-pika (Client):   Async Python library       │
│  ✅ Consumers:           Threads em asgi.py         │
│  ✅ Producers:           tasks.delay(queue, data)   │
│                                                      │
│  ❌ Celery:              NÃO É USADO                │
│  ❌ Celery Beat:         NÃO É USADO                │
│  ❌ Celery Worker:       NÃO É USADO                │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Como Funciona (Campanhas)

```python
# 1. PRODUCER - Enfileira tarefa
from apps.campaigns.tasks import enqueue_send_message

enqueue_send_message(
    campaign_id=str(campaign.id),
    contact_id=str(contact.id),
    message_text="Olá {{nome}}!"
)

# Isso vai para: backend/apps/campaigns/rabbitmq_consumer.py


# 2. CONSUMER - Processa fila (roda automáticamente)
# Ver: backend/alrea_sense/asgi.py (linhas 49-88)

def start_rabbitmq_consumer():
    from apps.campaigns.rabbitmq_consumer import get_rabbitmq_consumer
    consumer = get_rabbitmq_consumer()
    # Consumer processa mensagens automaticamente


# 3. PROCESSAMENTO - Execução assíncrona
class RabbitMQConsumer:
    async def _process_campaign_async(self, campaign_id):
        # Busca mensagens pendentes
        # Envia via Evolution API
        # Atualiza banco
        # Broadcast via WebSocket
```

### Filas RabbitMQ Ativas

```python
# CAMPANHAS
'campaign_send_message'     # Envio de mensagens de campanha
'campaign_scheduler'        # Agendamento de campanhas

# FLOW CHAT
'chat_send_message'         # Envio de mensagens do chat
'chat_download_attachment'  # Download de mídias do WhatsApp
'chat_migrate_s3'           # Migração de mídias para S3
'chat_fetch_profile_pic'    # Busca de fotos de perfil
```

---

## 🌐 WEBSOCKETS

### Implementação Atual

```yaml
Server: Daphne (ASGI)
Channel Layer: Redis (database 1)
Protocol: WebSocket (wss:// em prod)

Consumers Ativos:
  - ChatConsumer (apps.chat.consumers)
  - TenantChatConsumer (apps.chat.tenant_consumer)
  - CampaignConsumer (apps.chat_messages.consumers)
```

### Estrutura de Grupos

```python
# Chat por Conversa
chat_tenant_{tenant_id}_conversation_{conversation_id}

# Chat por Tenant (notificações globais)
chat_tenant_{tenant_id}

# Campanhas por Tenant
tenant_{tenant_id}
```

### Mensagens WebSocket

```typescript
// Frontend envia
{
  type: 'message_sent',
  data: {
    conversation_id: 'uuid',
    message_text: 'Olá!',
    direction: 'outgoing'
  }
}

// Backend responde
{
  type: 'message_received',
  data: {
    id: 'uuid',
    conversation_id: 'uuid',
    message_text: 'Olá!',
    created_at: '2025-10-20T12:00:00Z',
    status: 'sent'
  }
}
```

---

## 🔐 MULTI-TENANCY

### Isolamento de Dados

**Todo modelo crítico TEM `tenant_id`:**

```python
class Campaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    # ... outros campos

    class Meta:
        db_table = 'campaigns_campaign'
        ordering = ['-created_at']
```

### Filtros Automáticos

```python
# Middleware adiciona tenant ao request
class TenantMiddleware:
    def __call__(self, request):
        if request.user.is_authenticated:
            request.tenant = request.user.tenant

# ViewSets filtram automaticamente
class CampaignViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return Campaign.objects.filter(tenant=self.request.user.tenant)
```

### Permissões por Departamento

```python
# User roles
ROLE_CHOICES = [
    ('admin', 'Administrador'),      # Vê tudo do tenant
    ('manager', 'Gerente'),          # Vê seu departamento
    ('agent', 'Atendente'),          # Vê suas conversas
]

# Filtro por departamento
if user.role == 'manager':
    queryset = queryset.filter(department=user.department)
elif user.role == 'agent':
    queryset = queryset.filter(assigned_to=user)
```

---

## 🎨 FRONTEND - PADRÕES

### Estrutura de Módulos

```typescript
// Cada produto tem seu módulo
/modules
  /chat
    /components    # Componentes específicos do chat
    /hooks         # Hooks do chat (useChatSocket, etc)
    /stores        # Zustand store do chat
    /types         # TypeScript types
  /campaigns
    /components
    /hooks
    /stores
    /types
```

### Hooks Customizados

```typescript
// WebSocket Chat
import { useChatSocket } from '@/modules/chat/hooks/useChatSocket'
const { isConnected, sendMessage } = useChatSocket(conversationId)

// WebSocket Tenant (notificações globais)
import { useTenantSocket } from '@/modules/chat/hooks/useTenantSocket'
useTenantSocket() // Auto-conecta e gerencia toasts

// Campanhas
import { useCampaignWebSocket } from '@/hooks/useCampaignWebSocket'
const { lastUpdate, connectionStatus } = useCampaignWebSocket(onUpdate)
```

### State Management (Zustand)

```typescript
// Store global de autenticação
import { useAuthStore } from '@/stores/authStore'
const { user, token, login, logout } = useAuthStore()

// Store do chat
import { useChatStore } from '@/modules/chat/stores/chatStore'
const { conversations, addMessage, updateConversation } = useChatStore()
```

### Notificações (Sonner)

```typescript
import { toast } from 'sonner'

// Sucesso
toast.success('Mensagem enviada!', {
  description: 'A mensagem foi enviada para o WhatsApp'
})

// Erro
toast.error('Erro ao enviar', {
  description: 'Tente novamente em alguns instantes'
})

// Informação
toast.info('Nova mensagem', {
  description: 'Você recebeu uma mensagem de Paulo Bernal'
})
```

---

## 📦 PRODUTOS E PLANOS

### Produtos Disponíveis

```python
# backend/apps/tenancy/models.py

PRODUCT_CHOICES = [
    ('flow', 'Flow - Campanhas + Chat'),
    ('sense', 'Sense - Análise IA'),
    ('api', 'API Pública'),
    ('notifications', 'Notificações'),
]

# Cada produto pode ser:
- Base plan (incluído no plano)
- Addon (adicional pago)
```

### Planos

```python
PLAN_CHOICES = [
    ('starter', 'Starter'),           # 1 usuário, 1 instância
    ('professional', 'Professional'), # 5 usuários, 3 instâncias
    ('enterprise', 'Enterprise'),     # Ilimitado
    ('api_only', 'API Only'),         # Só API pública
]

# Limites configuráveis por plano
class TenantPlan:
    max_users = models.IntegerField(default=1)
    max_instances = models.IntegerField(default=1)
    max_contacts = models.IntegerField(default=1000)
    max_campaigns_per_month = models.IntegerField(default=10)
```

### Verificação de Acesso

```typescript
// Frontend - Hook de permissão
import { useUserAccess } from '@/hooks/useUserAccess'

const { canAccess, loading } = useUserAccess('flow')

if (!canAccess) {
  return <UpgradePrompt productSlug="flow" />
}
```

---

## 🔌 INTEGRAÇÃO EVOLUTION API

### Webhooks Recebidos

```python
# backend/apps/connections/webhook_views.py

EVENTOS_PROCESSADOS = [
    'messages.upsert',      # Nova mensagem recebida/enviada
    'messages.update',      # Status de mensagem (delivered/read)
    'contacts.update',      # Atualização de contato (foto, nome)
    'connection.update',    # Status da conexão WhatsApp
    'chats.update',         # Atualização de chat
]
```

### Fluxo de Processamento

```python
# 1. Webhook recebe evento
@csrf_exempt
def evolution_webhook(request):
    data = json.loads(request.body)
    event = data.get('event')
    
    # 2. Cache Redis (evitar duplicatas)
    cache_key = f"webhook_{tenant_id}_{event_id}"
    if cache.get(cache_key):
        return JsonResponse({'status': 'duplicate'})
    cache.set(cache_key, True, timeout=300)
    
    # 3. Processa evento
    if event == 'messages.upsert':
        handle_message_upsert(data, tenant)
    elif event == 'contacts.update':
        handle_contact_update(data, tenant)
    
    # 4. Broadcast via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_tenant_{tenant_id}',
        {
            'type': 'new_message',
            'data': message_data
        }
    )
    
    return JsonResponse({'status': 'ok'})
```

### Envio de Mensagens

```python
import httpx

async def send_whatsapp_message(instance_id, phone, message):
    url = f"{EVOLUTION_API_URL}/message/sendText/{instance_id}"
    
    headers = {
        'apikey': EVOLUTION_API_KEY,
        'Content-Type': 'application/json'
    }

    payload = {
        'number': phone,
        'text': message,
        'delay': 1200  # 1.2 segundos
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
```

---

## 💾 STORAGE (Mídia)

### Arquitetura de Mídia

```yaml
Permanente: MinIO/S3 (Railway)
  - Bucket: flow-attachments
  - Endpoint: https://bucket-production-8fb1.up.railway.app
  - Retenção: Ilimitada
  - Custo: ~$0.02/GB/mês

Cache: Redis (7 dias TTL)
  - Fotos de perfil
  - Mídias recentes do chat
  - Thumbnails

Temporário: Volume Railway (/mnt/storage/whatsapp/)
  - Downloads em processamento
  - Limpeza automática após 24h
```

### Proxy de Mídia

```python
# backend/apps/chat/views.py

@csrf_exempt
@require_http_methods(["GET"])
def media_proxy(request):
    """
    Proxy público para servir mídia (fotos, áudios, docs).
    
    IMPORTANTE: Este endpoint NÃO requer autenticação!
    Usado para exibir fotos de perfil e mídias no chat.
    """
    media_url = request.GET.get('url')
    
    # 1. Tentar Redis cache
    cache_key = f"media:{hashlib.md5(media_url.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    
    if cached:
        return HttpResponse(
            cached['content'],
            content_type=cached['content_type'],
            headers={'X-Cache': 'HIT'}
        )
    
    # 2. Baixar do S3/WhatsApp
    with httpx.Client(timeout=10.0) as client:
        response = client.get(media_url)
        content = response.content
        content_type = response.headers.get('content-type')
    
    # 3. Cachear no Redis (7 dias)
    cache.set(cache_key, {
        'content': content,
        'content_type': content_type
    }, timeout=604800)
    
    return HttpResponse(content, content_type=content_type)
```

---

## 🧪 TESTES E VALIDAÇÃO

### Regra de Ouro: SEMPRE TESTAR ANTES DE COMMIT

**⚠️ CRÍTICO: Verificação de Compatibilidade**

**ANTES de fazer commit/push, SEMPRE verificar:**

1. **✅ Compatibilidade com código existente**
   - Verificar se alterações não quebram funcionalidades existentes
   - Testar fluxos relacionados que podem ser afetados
   - Verificar se campos novos são nullable ou têm defaults seguros
   - Confirmar que migrations não vão quebrar dados existentes

2. **✅ Verificação de dependências**
   - Verificar se imports estão corretos
   - Confirmar que modelos/serializers não foram quebrados
   - Verificar se endpoints de API mantêm compatibilidade
   - Checar se frontend não quebra com mudanças no backend

3. **✅ Validação de dados**
   - Campos novos devem ser nullable ou ter defaults seguros
   - Migrations SQL devem usar `IF NOT EXISTS` e `IF EXISTS`
   - Verificar se queries não vão retornar erros com dados existentes
   - Confirmar que filtros por tenant continuam funcionando

4. **✅ Testes funcionais**
   - Testar funcionalidade modificada
   - Testar funcionalidades relacionadas que podem ser afetadas
   - Verificar logs para erros inesperados
   - Confirmar que WebSocket/real-time continua funcionando

**Checklist antes de commit:**
- [ ] Alterações não quebram código existente?
- [ ] Campos novos são nullable ou têm defaults?
- [ ] Migrations são seguras (IF NOT EXISTS)?
- [ ] Imports estão corretos?
- [ ] Endpoints mantêm compatibilidade?
- [ ] Filtros por tenant continuam funcionando?
- [ ] Funcionalidades relacionadas foram testadas?
- [ ] Logs não mostram erros inesperados?

### Regra de Ouro: SEMPRE TESTAR ANTES DE COMMIT

```bash
# [[memory:9724794]]
# CRÍTICO: Sempre criar scripts de teste ANTES de push!

# 1. Criar script de teste
python test_feature.py

# 2. Validar localmente
python manage.py runserver
# Testar todas as funcionalidades

# 3. Só então fazer commit
git add .
git commit -m "feat: nova funcionalidade"
git push origin main
```

### Scripts de Teste Recomendados

```python
# test_chat_flow.py - Testa chat completo
# test_campaign_send.py - Testa envio de campanhas
# test_webhook_events.py - Simula eventos do Evolution
# test_websocket_connection.py - Valida WebSocket
```

---

## 🚀 DEPLOY E PRODUÇÃO

### Railway Configuration

```yaml
Services:
  - Backend (Django + Daphne)
    Build: Dockerfile
    Start: Procfile web
    Env: Todas as env vars (DATABASE_URL, REDIS_URL, etc)
    
  - PostgreSQL 15
    Plugin: Railway PostgreSQL
    Extension: pgvector
    
  - Redis 7
    Plugin: Railway Redis
    Databases: 0 (cache), 1 (channels)
    
  - MinIO (S3)
    Plugin: Railway MinIO
    Bucket: flow-attachments
    
  - RabbitMQ
    Plugin: Railway RabbitMQ
    URL: RABBITMQ_PRIVATE_URL
```

### Variáveis de Ambiente Críticas

```bash
# Django
SECRET_KEY=<gerado>
DEBUG=False
ALLOWED_HOSTS=*.railway.app

# Database
DATABASE_URL=postgresql://...

# Redis
REDIS_URL=redis://...

# RabbitMQ
RABBITMQ_PRIVATE_URL=amqp://...

# Evolution API
EVOLUTION_API_URL=https://evo.rbtec.com.br
EVOLUTION_API_KEY=<chave>

# MinIO/S3
S3_ENDPOINT_URL=https://bucket-production-8fb1.up.railway.app
S3_ACCESS_KEY=<chave>
S3_SECRET_KEY=<chave>
S3_BUCKET=flow-attachments

# Stripe
STRIPE_SECRET_KEY=sk_...
STRIPE_PUBLISHABLE_KEY=pk_...

# Base URL
BASE_URL=https://alreasense-backend-production.up.railway.app
```

---

## 📝 BOAS PRÁTICAS

### Backend (Django)

```python
# ✅ SEMPRE usar UUID como PK
class Campaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

# ✅ SEMPRE adicionar tenant
class Campaign(models.Model):
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE)

# ✅ SEMPRE usar timezone.now()
from django.utils import timezone
created_at = models.DateTimeField(default=timezone.now)

# ✅ SEMPRE logar eventos importantes
import logging
logger = logging.getLogger(__name__)
logger.info(f'✅ Campanha {campaign.name} iniciada')

# ❌ NUNCA usar print() (usar logger)
# ❌ NUNCA criar models sem tenant
# ❌ NUNCA usar datetime.now() (usar timezone.now)
```

### Frontend (React/TypeScript)

```typescript
// ✅ SEMPRE tipar props e states
interface ChatWindowProps {
  conversationId: string
  onClose: () => void
}

// ✅ SEMPRE usar hooks personalizados
const { isConnected, sendMessage } = useChatSocket(conversationId)

// ✅ SEMPRE tratar erros
try {
  await api.post('/messages/', data)
  toast.success('Mensagem enviada!')
} catch (error) {
  toast.error('Erro ao enviar mensagem')
  console.error(error)
}

// ❌ NUNCA usar any (sempre tipar)
// ❌ NUNCA fazer fetch direto (usar axios com interceptors)
// ❌ NUNCA esquecer de desconectar WebSocket no cleanup
```

### WebSockets

```typescript
// ✅ SEMPRE desconectar no cleanup
useEffect(() => {
  const ws = new WebSocket(wsUrl)
  
  return () => {
    ws.close()
  }
}, [])

// ✅ SEMPRE implementar reconexão
const reconnect = () => {
  if (reconnectAttempts < MAX_RETRIES) {
    setTimeout(connect, 3000 * reconnectAttempts)
  }
}

// ✅ SEMPRE ter fallback (polling)
if (connectionStatus === 'error') {
  startPolling()
}
```

---

## 🔍 TROUBLESHOOTING

### Problemas Comuns

#### 1. WebSocket não conecta

```bash
# Verificar se Daphne está rodando
curl https://alreasense-backend-production.up.railway.app/api/health/

# Verificar logs do Railway
railway logs

# Verificar Redis Channel Layer
python manage.py shell
>>> from channels.layers import get_channel_layer
>>> channel_layer = get_channel_layer()
>>> await channel_layer.send('test', {'type': 'test'})
```

#### 2. RabbitMQ não processa filas

```python
# Verificar se consumer está rodando
# Ver logs do asgi.py no Railway

# Forçar iniciar consumer manualmente
from apps.campaigns.rabbitmq_consumer import get_rabbitmq_consumer
consumer = get_rabbitmq_consumer()
consumer.start_campaign('campaign-uuid')
```

#### 3. Mídia não carrega

```bash
# Verificar proxy endpoint
curl "https://backend.railway.app/api/chat/media-proxy/?url=https://..."

# Verificar Redis cache
redis-cli
> GET "media:abc123..."

# Verificar MinIO
aws s3 ls s3://flow-attachments --endpoint-url=...
```

---

## 📚 DOCUMENTAÇÃO ADICIONAL

### Arquivos de Referência

```
ALREA_CAMPAIGNS_TECHNICAL_SPEC.md    # Spec completa de campanhas
IMPLEMENTACAO_SISTEMA_MIDIA.md       # Sistema de mídia (fotos, docs)
ANALISE_COMPLETA_PROJETO_2025.md     # Análise arquitetural
WEBSOCKET_CAMPAIGNS.md               # WebSocket de campanhas
COMO_TESTAR_ANTES_DE_COMMIT.md       # Guia de testes
```

### Diagramas Úteis

```
docs/ARCHITECTURE.md      # Diagrama geral
docs/DB_SCHEMA.md         # Schema do banco
docs/DEPLOYMENT.md        # Guia de deploy
```

---

## ⚡ QUICK REFERENCE

### Comandos Essenciais

```bash
# Backend - Local
python manage.py runserver
python manage.py migrate
python manage.py shell

# Frontend - Local
npm run dev
npm run build

# Deploy - Railway
git push origin main  # Auto-deploy

# Logs - Railway
railway logs --tail
```

### URLs Importantes

```
Produção:
  Frontend: https://alreasense-production.up.railway.app
  Backend:  https://alreasense-backend-production.up.railway.app
  Admin:    https://alreasense-backend-production.up.railway.app/admin

Local:
  Frontend: http://localhost:5173
  Backend:  http://localhost:8000
  Admin:    http://localhost:8000/admin
```

---

## 🎯 MISSÃO DO PROJETO

> **"Fornecer uma plataforma SaaS robusta, escalável e multi-tenant para gestão de campanhas WhatsApp e atendimento em tempo real, com foco em performance, UX impecável e código maintainável."**

### Princípios

1. **Multi-tenancy First** - Isolamento total de dados
2. **Real-time Everything** - WebSocket para tudo que importa
3. **Async by Default** - RabbitMQ para processamento pesado
4. **Test Before Push** - [[memory:9724794]] Sempre testar localmente
5. **User Experience** - Feedback visual constante (toasts, loading, errors)
6. **Clean Code** - Código legível > Código "esperto"

---

## 🛡️ REGRA CRÍTICA: PRESERVAÇÃO DE CÓDIGO EXISTENTE

### ⚠️ PRINCÍPIO FUNDAMENTAL

**NENHUMA MODIFICAÇÃO PODE QUEBRAR O CÓDIGO JÁ EXISTENTE**

Esta é uma regra **NÃO NEGOCIÁVEL** e deve ser seguida em **TODAS** as alterações.

### Regras Obrigatórias

1. **✅ SEMPRE testar funcionalidades existentes antes de modificar**
   ```bash
   # Antes de qualquer mudança:
   # 1. Testar funcionalidade atual
   # 2. Fazer alteração
   # 3. Testar novamente que ainda funciona
   # 4. Testar nova funcionalidade
   ```

2. **✅ SEMPRE manter compatibilidade retroativa**
   - Endpoints existentes devem continuar funcionando
   - Estruturas de dados não devem mudar sem migração
   - APIs públicas não devem quebrar contratos existentes

3. **✅ SEMPRE usar feature flags para mudanças grandes**
   ```python
   # Exemplo: Nova funcionalidade opcional
   if settings.ENABLE_NEW_FEATURE:
       # Nova lógica
   else:
       # Lógica antiga (mantém funcionando)
   ```

4. **✅ SEMPRE fazer refatoração incremental**
   - Não refatorar tudo de uma vez
   - Fazer mudanças pequenas e testáveis
   - Manter código antigo funcionando enquanto migra

5. **✅ SEMPRE verificar dependências antes de remover**
   ```bash
   # Antes de remover código:
   # 1. Buscar todas as referências
   grep -r "funcao_antiga" backend/
   # 2. Verificar se está sendo usado
   # 3. Se sim, criar alternativa antes de remover
   ```

6. **✅ SEMPRE documentar breaking changes**
   ```markdown
   ## BREAKING CHANGE
   - Endpoint `/api/old/` foi removido
   - Use `/api/new/` ao invés
   - Migração automática disponível em `/api/migrate/`
   ```

### Checklist Antes de Commitar

- [ ] Funcionalidades existentes ainda funcionam?
- [ ] Testes existentes ainda passam?
- [ ] Não quebrei nenhum endpoint público?
- [ ] Não removi código que ainda é usado?
- [ ] Documentei mudanças que podem afetar outros?
- [ ] Criei migração se necessário?
- [ ] Testei localmente antes de push?

### Exemplos de Violações

```python
# ❌ ERRADO: Remover endpoint sem aviso
# @api_view(['POST'])
# def old_endpoint(request):
#     ...

# ✅ CORRETO: Deprecar primeiro, depois remover
@api_view(['POST'])
@deprecated("Use /api/new/ ao invés. Será removido em 2026-01-01")
def old_endpoint(request):
    ...
```

```typescript
// ❌ ERRADO: Mudar estrutura sem aviso
interface Message {
  // content: string  // Removido!
  text: string  // Novo
}

// ✅ CORRETO: Manter compatibilidade
interface Message {
  content?: string  // Deprecated, use text
  text: string      // Novo
}
```

### Consequências de Quebrar Código

1. **Rollback imediato** - Mudança será revertida
2. **Análise de impacto** - Verificar o que foi afetado
3. **Correção prioritária** - Fix deve ser feito imediatamente
4. **Documentação** - Registrar o que aconteceu e por quê

### Exceções (Raríssimas)

Apenas em casos **EXTREMAMENTE CRÍTICOS** de segurança ou bugs graves que afetam produção:

1. Bug de segurança que expõe dados
2. Bug que corrompe dados no banco
3. Bug que quebra funcionalidade crítica de produção

**Mesmo nestes casos:**
- Documentar claramente o motivo
- Criar plano de migração
- Notificar usuários afetados
- Fazer rollback se possível

---

**Última atualização:** 5 de Dezembro de 2025  
**Mantido por:** Time de Desenvolvimento ALREA Sense
