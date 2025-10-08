# 🚦 EVO SENSE — RULES OF DEVELOPMENT

## 🧭 Visão Geral
EvoSense é uma plataforma **SaaS multi-tenant** para análise de sentimento e satisfação de clientes em conversas do WhatsApp (Evolution API).  

**Stack principal:**
- **Backend:** Django 5 + DRF + Channels + Celery
- **Frontend:** React + TypeScript + Vite + Tailwind + shadcn/ui
- **Banco:** PostgreSQL + pgvector
- **Infra:** Docker + Railway
- **IA:** via MCP (n8n HTTP) ou modelo local (Qwen/Ollama)
- **Billing:** Stripe (30 dias)
- **Realtime:** Django Channels (WebSocket)
- **Experimentos:** versionamento de prompts e shadow inference

---

## 🧱 Arquitetura

### Estrutura de monorepo:
```
/evosense
  /backend
    manage.py
    evosense/settings.py
    evosense/asgi.py
    evosense/celery.py
    /apps
      /tenancy
      /authn
      /connections
      /messages
      /ai
      /billing
      /experiments
    /ingestion
      evolution_ws.py
    /common
      utils.py
      permissions.py
    requirements.txt
    Dockerfile
  /frontend
    src/...
    index.html
    package.json
    vite.config.ts
    Dockerfile
  /docs
    ARCHITECTURE.md
    DB_SCHEMA.md
    DEPLOYMENT.md
  docker-compose.yml
  README.md
```

### Infraestrutura:
- **Banco:** PostgreSQL 15+ (Railway) com extensão `pgvector`
- **Processos assíncronos:** Celery + Redis
- **Eventos em tempo real:** Channels (Redis layer)
- **Deploy:** Railway Docker service

---

## 🔐 Multi-tenancy e Segurança

### Isolamento de dados:
- Cada modelo tem `tenant_id` (FK → Tenant)
- `User` customizado (extends `AbstractUser`) com `tenant` e `role (admin/operator)`
- Todas as queries filtram por `tenant_id`
- WebSockets segregados por tenant: `/ws/tenant/<tenant_id>/`

### Segurança:
- Dados sensíveis (tokens Evolution, Stripe) são criptografados
- JWT/Session Auth padrão DRF
- Sanitização de mensagens (regex para PII: CPF, email, cartão)
- Rate limiting nos endpoints públicos
- CORS configurado apenas para domínios do cliente
- HTTPS obrigatório em produção

---

## 🗃️ Modelos (Django ORM)

### tenancy.Tenant
```python
class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    plan = models.CharField(max_length=32, default="starter")  # starter|pro|scale|enterprise
    next_billing_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, default="active")  # active|suspended
    created_at = models.DateTimeField(auto_now_add=True)
```

### authn.User (extends AbstractUser)
```python
class User(AbstractUser):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="users")
    role = models.CharField(max_length=16, default="operator")  # admin|operator
```

### connections.EvolutionConnection
```python
class EvolutionConnection(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="connections")
    name = models.CharField(max_length=80)
    evo_ws_url = models.URLField()
    evo_token = models.CharField(max_length=255)  # criptografado
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### messages.Message
```python
class Message(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="messages")
    connection = models.ForeignKey('connections.EvolutionConnection', on_delete=models.SET_NULL, null=True)
    chat_id = models.CharField(max_length=128, db_index=True)
    sender = models.CharField(max_length=64)    # hash do número/ID
    text = models.TextField()
    created_at = models.DateTimeField(db_index=True)
    
    # Resultados IA
    sentiment = models.FloatField(null=True, blank=True)     # -1..1
    emotion = models.CharField(max_length=40, null=True, blank=True)
    satisfaction = models.IntegerField(null=True, blank=True) # 0..100
    tone = models.CharField(max_length=40, null=True, blank=True)
    summary = models.CharField(max_length=200, null=True, blank=True)
    
    # pgvector
    embedding = models.BinaryField(null=True, blank=True)  # implementar via SQL raw helper

    class Meta:
        indexes = [GinIndex(fields=['text'])]  # full-text fallback
```

### experiments.PromptTemplate
```python
class PromptTemplate(models.Model):
    version = models.CharField(max_length=64, unique=True)
    body = models.TextField()  # texto do prompt
    created_at = models.DateTimeField(auto_now_add=True)
```

### experiments.Inference
```python
class Inference(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="inferences")
    model_name = models.CharField(max_length=64)         # qwen-X, ollama-qwen2...
    prompt_version = models.CharField(max_length=64)
    template_hash = models.CharField(max_length=64)
    latency_ms = models.IntegerField()
    sentiment = models.FloatField()
    emotion = models.CharField(max_length=40)
    satisfaction = models.IntegerField()
    is_shadow = models.BooleanField(default=False)
    run_id = models.CharField(max_length=64, db_index=True)  # experimento
    created_at = models.DateTimeField(auto_now_add=True)
```

### billing.PaymentAccount
```python
class PaymentAccount(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    stripe_customer_id = models.CharField(max_length=255)
    status = models.CharField(max_length=16, default="active")  # active|expired|pending
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## 🗄️ pgvector

### Configuração:
```sql
-- Migration inicial
CREATE EXTENSION IF NOT EXISTS vector;

-- Adicionar coluna embedding (768 dims - ajuste conforme encoder)
ALTER TABLE messages_message ADD COLUMN embedding vector(768);

-- Índice IVFFLAT
CREATE INDEX IF NOT EXISTS idx_message_embedding
  ON messages_message USING ivfflat (embedding vector_cosine) WITH (lists = 100);
```

### DAO helpers:
```python
# apps/messages/dao.py
from django.db import connection

def write_embedding(message_id: int, emb: list[float]):
    vec = "[" + ",".join(f"{x:.6f}" for x in emb) + "]"
    with connection.cursor() as cur:
        cur.execute("UPDATE messages_message SET embedding = %s::vector WHERE id = %s", [vec, message_id])

def semantic_search(tenant_id, query_emb, limit=20):
    vec = "[" + ",".join(f"{x:.6f}" for x in query_emb) + "]"
    with connection.cursor() as cur:
        cur.execute("""
            SELECT id, text, sentiment, satisfaction
            FROM messages_message
            WHERE tenant_id = %s
            ORDER BY embedding <-> %s::vector
            LIMIT %s
        """, [str(tenant_id), vec, limit])
        rows = cur.fetchall()
    return rows
```

---

## 📡 Ingestão Evolution (WebSocket)

### evolution_ws.py:
```python
import asyncio, json, websockets, datetime
from django.utils import timezone
from apps.messages.models import Message
from apps.ai.tasks import analyze_message_async

async def listen_connection(conn):
    headers = [("Authorization", f"Bearer {conn.evo_token}")]
    async with websockets.connect(conn.evo_ws_url, extra_headers=headers) as ws:
        async for raw in ws:
            evt = json.loads(raw)
            if evt.get("type") == "message":
                msg = Message.objects.create(
                    tenant=conn.tenant,
                    connection=conn,
                    chat_id=evt["chatId"],
                    sender=evt["from"],
                    text=evt["body"],
                    created_at=timezone.now()
                )
                analyze_message_async.delay(str(conn.tenant_id), msg.id)  # Celery

async def main():
    from apps.connections.models import EvolutionConnection
    conns = EvolutionConnection.objects.filter(is_active=True)
    await asyncio.gather(*(listen_connection(c) for c in conns))
```

---

## 🧠 IA via MCP (n8n HTTP) / HTTP local

### Configuração:
- Webhook HTTP configurável (`N8N_AI_WEBHOOK`)
- Timeout + retries (3x) com backoff
- Payload estruturado:

```json
{
  "tenant_id": "...",
  "message": "texto",
  "context": { "chat_id": "...", "sender": "..." },
  "prompt_version": "p_v1_base"
}
```

### Retorno esperado:
```json
{
  "sentiment": 0.72,
  "emotion": "positivo",
  "satisfaction": 85,
  "tone": "cordial",
  "summary": "Cliente satisfeito com a resposta."
}
```

### Celery task:
```python
@shared_task
def analyze_message_async(tenant_id, message_id, prompt_version=None, is_shadow=False, run_id="prod"):
    msg = Message.objects.get(id=message_id)
    template = PromptTemplate.objects.order_by('-created_at').first() if not prompt_version \
        else PromptTemplate.objects.get(version=prompt_version)

    payload = {
        "tenant_id": tenant_id,
        "message": msg.text,
        "context": {"chat_id": msg.chat_id, "sender": msg.sender},
        "prompt_version": template.version
    }
    
    t0 = time.time()
    r = requests.post(settings.N8N_AI_WEBHOOK, json=payload, timeout=3.0)
    r.raise_for_status()
    data = r.json()
    latency = int((time.time() - t0) * 1000)

    # Persistir no Message (apenas campeão) e sempre na tabela de Inference
    if not is_shadow:
        msg.sentiment = data["sentiment"]
        msg.emotion = data["emotion"]
        msg.satisfaction = data["satisfaction"]
        msg.tone = data.get("tone")
        msg.summary = data.get("summary")
        msg.save(update_fields=["sentiment","emotion","satisfaction","tone","summary"])

    # Embedding (opcional por plano)
    try:
        emb = embed_text(msg.text)
        write_embedding(msg.id, emb)
    except Exception:
        pass

    Inference.objects.create(
        tenant_id=tenant_id, message=msg, model_name=data.get("model","qwen-local"),
        prompt_version=template.version, template_hash="...", latency_ms=latency,
        sentiment=data["sentiment"], emotion=data["emotion"],
        satisfaction=data["satisfaction"], is_shadow=is_shadow, run_id=run_id
    )
```

---

## 🔁 Experimentos (replay & shadow)

### Backfill (replay com outro prompt):
```python
@shared_task
def replay_window(tenant_id, start_iso, end_iso, prompt_version, run_id):
    qs = Message.objects.filter(tenant_id=tenant_id, created_at__range=[start_iso, end_iso]).values_list("id", flat=True)
    for mid in qs:
        analyze_message_async.delay(tenant_id, mid, prompt_version=prompt_version, is_shadow=True, run_id=run_id)
```

### Champion/Challenger:
- Em produção: `champion/challenger` (90/10) controlado por tabela `PromptTemplate`
- O *campeão* preenche `Message`
- O *challenger* grava só em `Inference`

---

## 🧾 Billing (Stripe)

### Planos e limites:
| Plano | Conexões | Retenção | Preço (BRL) |
|-------|----------|----------|-------------|
| Starter | 1 | 30 dias | 199 |
| Pro | 3 | 180 dias | 499 |
| Scale | 6 | 365 dias | 999 |
| Enterprise | custom | 2 anos | sob contrato |

### Cron diário:
- Checar `next_billing_date` e criar cobrança
- Se falhar, `status = suspended` no tenant
- Webhook Stripe: eventos de pagamento (invoice.paid/failed)

---

## 🌐 API (DRF) — endpoints obrigatórios

### Autenticação:
- `POST /api/auth/login` | `GET /api/me`

### Core:
- `GET /api/tenants/:id/metrics` (médias, volumes, p95 latência)
- `GET /api/messages?chat_id=&q=&page=...` (páginação + FTS)
- `POST /api/messages/semantic-search` { query } → top-K via pgvector
- `GET/POST /api/connections`

### Experimentos:
- `GET/POST /api/prompts` (registrar novas versões)
- `POST /api/experiments/replay` (admin)
- `POST /api/ai/analyze` (admin)

### Webhooks:
- `POST /api/webhooks/stripe`
- (Opcional) `POST /api/webhooks/evolution` como fallback HTTP

### Health:
- `/health`

### Exemplo View (semantic search):
```python
# apps/messages/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.messages.dao import semantic_search
from apps.ai.embeddings import embed_text

class SemanticSearchView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        tenant_id = request.user.tenant_id
        query = request.data.get("query", "")
        emb = embed_text(query)  # chama seu encoder local via n8n/HTTP
        rows = semantic_search(tenant_id, emb, limit=20)
        return Response({"results": [
            {"id": r[0], "text": r[1], "sentiment": r[2], "satisfaction": r[3]}
            for r in rows
        ]})
```

---

## 🔌 WebSockets (Channels)

### routing.py:
```python
from django.urls import re_path
from .consumers import TenantConsumer

websocket_urlpatterns = [
    re_path(r'ws/tenant/(?P<tenant_id>[^/]+)/$', TenantConsumer.as_asgi()),
]
```

### consumers.py:
```python
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class TenantConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']
        self.group = f"tenant_{self.tenant_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def message_analyzed(self, event):
        await self.send_json(event["payload"])
```

### Emitir eventos após análise IA:
```python
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
layer = get_channel_layer()
async_to_sync(layer.group_send)(f"tenant_{tenant_id}", {
  "type": "message_analyzed",
  "payload": {"message_id": msg.id, "sentiment": msg.sentiment, "satisfaction": msg.satisfaction}
})
```

---

## 🧰 Frontend (React)

### Páginas obrigatórias:
- Login (JWT) + Painel principal
- Dashboard de KPIs (média de satisfação, % positivas, mensagens/dia)
- Conversas (lista + detalhe)
- Busca semântica (input → /api/messages/semantic-search)
- Aba de conexões Evolution
- Aba de experimentos (prompts + comparativos)
- Billing (plano atual, cobrança Stripe)

### WebSocket hook:
```typescript
import { useEffect, useRef } from 'react';

export function useTenantWS(tenantId: string) {
  const ref = useRef<WebSocket | null>(null);
  useEffect(() => {
    const ws = new WebSocket(`${import.meta.env.VITE_WS_BASE}/ws/tenant/${tenantId}/`);
    ref.current = ws;
    ws.onmessage = (e) => {
      const evt = JSON.parse(e.data);
      // atualizar store com evt.payload
    };
    return () => ws.close();
  }, [tenantId]);
}
```

### Stack:
- Tailwind + shadcn para UI
- Zustand para estado global
- Conectar WS: `ws://<backend>/ws/tenant/<tenant_id>/`

---

## ⚙️ Configuração & Deploy (Railway)

### .env.example:
```env
DJANGO_SECRET_KEY=
DATABASE_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://host:port/0
STRIPE_SECRET_KEY=
N8N_AI_WEBHOOK=https://<n8n>/webhook/ai-analysis
EVO_BASE_URL=
ALLOWED_HOSTS=*
```

### Comandos de deploy:
- Railway Postgres: rodar `CREATE EXTENSION IF NOT EXISTS vector;` uma única vez
- Backend: `python manage.py migrate && daphne -b 0.0.0.0 -p 8000 evosense.asgi:application`
- Celery: `celery -A evosense worker -l info` e `celery -A evosense beat -l info`
- Frontend: `npm run build && npm run preview -- --host 0.0.0.0 --port 5173`

### Docker Compose (local):
```yaml
version: "3.9"
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: evosense
    ports: ["5432:5432"]
  redis:
    image: redis:7
    ports: ["6379:6379"]
  backend:
    build: ./backend
    env_file: ./backend/.env
    depends_on: [db, redis]
    ports: ["8000:8000"]
  frontend:
    build: ./frontend
    ports: ["5173:5173"]
```

---

## 🧪 Qualidade & Observabilidade

### Linters:
- **Python:** Black + Ruff + isort
- **JS/TS:** ESLint + Prettier

### Logs:
- Logs estruturados JSON (loguru)
- Request-id/tenant-id em todas as requisições
- Métricas básicas: requisições, latência IA, volume de mensagens

### Healthchecks:
- `/health` backend
- WS ping/pong
- `/metrics` (Prometheus-style)

### Testes:
- Unit de services/DAO
- E2E básicos de API
- pytest + DRF test client

---

## 🧠 Estratégia de IA local

### Modelo:
- Qwen (rodando on-prem ou Ollama)
- Custo por mensagem: ~zero
- Quantização INT4/INT8 + batching

### Embeddings:
- Qwen-mini ou Ollama embedding model
- 768 dimensões (ajustar conforme modelo)

### Experimentos:
- Repositório de experimentos versionado (prompt_vN)
- Guardar dataset de treino interno para futuras calibrações

---

## ✅ Regras finais

### Segurança:
- Nenhum dado cru de cliente fora do banco
- Cada Tenant isolado em queries e permissões
- Testar todos os endpoints críticos com JWT
- IA deve sempre retornar JSON estrito e validado

### Performance:
- pgvector usado apenas para busca, não para storage primário
- Só salvar texto bruto de mensagens se plano permitir
- Rate limiting nos endpoints públicos

### Código:
- Nomenclatura consistente (snake_case backend, camelCase frontend)
- Módulos separados por domínio (clean architecture)
- Padrão de commits: Conventional Commits
- Nenhum dado sensível em logs

---

## 🎯 Objetivos do projeto

1. **Ingestão**: consumir mensagens da Evolution API (por tenant/connection), persistir, enviar à IA e armazenar resultados
2. **IA**: classificar `sentiment` (-1..1), `emotion`, `satisfaction` (0..100), `tone`, `summary`
3. **Busca semântica**: indexar embeddings em `pgvector` e expor endpoint de semantic search
4. **Multi-tenant**: isolar dados por tenant; impor limites por plano (nº de connections, retenção, exports/dia)
5. **Billing**: Stripe (planos Starter/Pro/Scale/Enterprise), cron diário, suspensão ao falhar cobrança
6. **Experimentos**: registrar `prompt_version`, rodar replay/backfill, shadow online e métricas comparativas
7. **Frontend**: autenticação, dashboard de KPIs, lista de conversas, detalhe, conexões, billing, experimentos; realtime via Channels

> **Objetivo final:** código pronto para subir no Railway, com ingestão Evolution, IA via MCP/HTTP, busca semântica, multi-tenant, billing e experimentos de prompt.
