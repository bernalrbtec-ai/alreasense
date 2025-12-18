# 🎯 **REGRAS E DECISÕES - SISTEMA DE BILLING**

> **Documento de referência para desenvolvimento**  
> **Use este arquivo como guia durante toda a implementação**

---

## 📋 **ÍNDICE**

1. [Decisões Arquiteturais](#decisões-arquiteturais)
2. [Reutilização de Código](#reutilização-de-código)
3. [Padrões de Código](#padrões-de-código)
4. [Estrutura de Pastas](#estrutura-de-pastas)
5. [Evolution API Service](#evolution-api-service)
6. [Models e Relacionamentos](#models-e-relacionamentos)
7. [Services e Utils](#services-e-utils)
8. [RabbitMQ e Workers](#rabbitmq-e-workers)
9. [APIs e Endpoints](#apis-e-endpoints)
10. [Segurança e Validação](#segurança-e-validação)
11. [Performance e Otimização](#performance-e-otimização)
12. [Testes e Qualidade](#testes-e-qualidade)
13. [Checklist de Implementação](#checklist-de-implementação)

---

## 🏗️ **DECISÕES ARQUITETURAIS**

### **✅ ARQUITETURA APROVADA:**

```
Cliente Externo (ERP/CRM)
    ↓ POST /api/v1/billing/send/overdue
Django REST API (Autenticação + Rate Limiting)
    ↓
BillingCampaignService (Orchestrator)
    ↓ Cria Campaign + BillingCampaign + BillingQueue
RabbitMQ (Message Broker)
    ↓ Publica em queue com prioridade
BillingConsumer (aio-pika)
    ↓ Consome mensagem
BillingSenderWorker (Sync Worker)
    ↓ Processa em batches
EvolutionAPIService (Serviço Centralizado) ← NOVO!
    ↓ Envia via WhatsApp
Evolution API
    ↓
Chat System (Salva histórico)
```

### **⚠️ REGRAS CRÍTICAS:**

1. **NÃO USAR CELERY** - Projeto usa RabbitMQ + aio-pika
2. **NÃO DUPLICAR CÓDIGO** - Reutilizar o máximo possível
3. **MULTI-TENANT FIRST** - Todo model precisa de `tenant_id`
4. **WEBSOCKET PARA REAL-TIME** - Usar Channels, não polling
5. **SEGURANÇA PRIMEIRO** - Validação, sanitização, rate limiting

---

## 🔄 **REUTILIZAÇÃO DE CÓDIGO**

### **✅ REUTILIZAR 100% (sem mudanças):**

| Componente | Arquivo Existente | Como Usar |
|------------|-------------------|-----------|
| **Phone Validation** | `apps/contacts/utils.py::normalize_phone` | `from apps.contacts.utils import normalize_phone` |
| **Business Hours** | `apps/chat/services/business_hours_service.py` | `from apps.chat.services.business_hours_service import BusinessHoursService` |
| **Rate Limiting** | `apps/common/rate_limiting.py` | `from apps.common.rate_limiting import rate_limit_by_ip` |
| **Business Hours Model** | `apps/chat/models_business_hours.py::BusinessHours` | `from apps.chat.models_business_hours import BusinessHours` |

### **⚠️ ADAPTAR (pequenas mudanças):**

| Componente | Arquivo Existente | O Que Adaptar |
|------------|-------------------|---------------|
| **Template Engine** | `apps/campaigns/services.py::MessageVariableService` | Criar `BillingTemplateEngine` separado (suporta condicionais `{{#if}}`) |
| **RabbitMQ Consumer** | `apps/campaigns/rabbitmq_consumer.py` | Adaptar para múltiplas queues + prioridades |

### **✅ CRIAR DO ZERO:**

- ✅ Todos os 6 models de billing
- ✅ `BillingCampaignService` (orchestrator)
- ✅ `BillingSendService` (envio)
- ✅ `BillingTemplateEngine` (com condicionais)
- ✅ `BillingSenderWorker` (worker)
- ✅ `BillingConsumer` (RabbitMQ)
- ✅ `EvolutionAPIService` (serviço centralizado) ← **NOVO!**
- ✅ APIs REST (5 endpoints)
- ✅ Serializers

---

## 📁 **ESTRUTURA DE PASTAS**

### **Estrutura Completa:**

```
backend/apps/billing/
├── __init__.py
├── apps.py
├── admin.py
│
├── models/
│   ├── __init__.py
│   ├── billing_config.py
│   ├── billing_api_key.py
│   ├── billing_template.py
│   ├── billing_campaign.py
│   ├── billing_queue.py
│   └── billing_contact.py
│
├── services/
│   ├── __init__.py
│   ├── billing_campaign_service.py
│   ├── billing_send_service.py
│   └── instance_checker.py
│
├── utils/
│   ├── __init__.py
│   ├── template_engine.py  # ← NOVO (com condicionais)
│   ├── date_calculator.py
│   └── template_sanitizer.py
│
├── schedulers/
│   ├── __init__.py
│   └── business_hours_scheduler.py  # ← Wrapper do BusinessHoursService
│
├── workers/
│   ├── __init__.py
│   └── billing_sender_worker.py
│
├── rabbitmq/
│   ├── __init__.py
│   ├── billing_publisher.py
│   └── billing_consumer.py
│
├── management/
│   └── commands/
│       ├── __init__.py
│       ├── run_billing_consumer.py
│       └── run_billing_periodic_tasks.py
│
├── migrations/
│   └── __init__.py
│
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_services.py
│   ├── test_utils.py
│   ├── test_worker.py
│   └── test_api.py
│
├── constants.py
├── metrics.py
├── authentication.py
├── throttling.py
├── serializers.py
├── views.py
└── urls.py
```

### **⚠️ IMPORTANTE:**

- ✅ `utils/template_engine.py` é NOVO (não reutiliza MessageVariableService)
- ✅ `schedulers/business_hours_scheduler.py` é wrapper (reutiliza BusinessHoursService)
- ✅ `utils/phone_validator.py` NÃO CRIAR (usar `contacts/utils.py`)

---

## 🔧 **EVOLUTION API SERVICE**

### **✅ DECISÃO: CRIAR SERVIÇO CENTRALIZADO AGORA**

**📄 Documentação Completa:** [EVOLUTION_API_SERVICE_SPEC.md](./EVOLUTION_API_SERVICE_SPEC.md)

**Arquivo:** `apps/common/services/evolution_api_service.py`

**Motivos:**
- ✅ Billing é novo → começar certo desde o início
- ✅ Facilita melhorias futuras (health check, circuit breaker)
- ✅ Código mais limpo e testável
- ✅ Migração gradual depois (campanhas, chat, notificações)

### **Resumo Rápido:**

```python
# apps/common/services/evolution_api_service.py

from apps.common.services.evolution_api_service import EvolutionAPIService

# Uso:
evolution = EvolutionAPIService(instance)
success, response = evolution.send_text_message(
    phone='+5511999999999',
    message='Olá!',
    retry=True,
    max_retries=3
)
```

### **Features Principais:**

- ✅ Retry automático com backoff exponencial
- ✅ Health check de instância (`check_health()`)
- ✅ Normalização de telefone (reutiliza `contacts/utils.py`)
- ✅ Error handling robusto
- ✅ Logging estruturado
- ⏳ Rate limiting por instância (futuro)
- ⏳ Métricas Prometheus (futuro)
- ⏳ Circuit breaker (futuro)

### **Uso em Billing:**

```python
# apps/billing/services/billing_send_service.py

from apps.common.services.evolution_api_service import EvolutionAPIService

class BillingSendService:
    def send_billing_message(self, billing_contact, instance):
        evolution = EvolutionAPIService(instance)
        
        success, response = evolution.send_text_message(
            phone=billing_contact.campaign_contact.phone_number,
            message=billing_contact.rendered_message,
            retry=True,
            max_retries=3
        )
        
        if success:
            # Salva no chat, atualiza status, etc.
            pass
```

### **Migração Futura:**

**Ordem sugerida:**
1. ✅ Billing (agora) - primeiro uso
2. ⏳ Campanhas (depois) - PR separado
3. ⏳ Notificações (depois) - PR separado
4. ⏳ Chat (por último) - mais crítico

**📄 Ver detalhes completos:** [EVOLUTION_API_SERVICE_SPEC.md](./EVOLUTION_API_SERVICE_SPEC.md)

---

## 📦 **MODELS E RELACIONAMENTOS**

### **Models a Criar:**

1. **BillingConfig** (`models/billing_config.py`)
   - OneToOne com Tenant
   - Configurações de throttling, horário comercial, limites

2. **BillingAPIKey** (`models/billing_api_key.py`)
   - ForeignKey para Tenant
   - API Keys para acesso externo

3. **BillingTemplate** (`models/billing_template.py`)
   - ForeignKey para Tenant
   - Templates de mensagem (overdue, upcoming, notification)

4. **BillingTemplateVariation** (`models/billing_template.py`)
   - ForeignKey para BillingTemplate
   - Até 5 variações por template (anti-bloqueio)

5. **BillingCampaign** (`models/billing_campaign.py`)
   - ForeignKey para Tenant
   - OneToOne com Campaign (reutiliza model existente!)
   - ForeignKey para BillingTemplate

6. **BillingQueue** (`models/billing_queue.py`)
   - OneToOne com BillingCampaign
   - Controle de fila de processamento

7. **BillingContact** (`models/billing_contact.py`)
   - ForeignKey para BillingCampaign
   - OneToOne com CampaignContact (reutiliza model existente!)
   - ForeignKey para BillingTemplateVariation

### **⚠️ REGRAS DE RELACIONAMENTOS:**

- ✅ **BillingCampaign** usa `Campaign` existente (OneToOne)
- ✅ **BillingContact** usa `CampaignContact` existente (OneToOne)
- ✅ **BusinessHours** usa model existente (`apps/chat/models_business_hours.py`)
- ✅ Todos os models têm `tenant` (multi-tenant)

### **Indexes Obrigatórios:**

```python
# Em cada model Meta:
indexes = [
    models.Index(fields=['tenant', 'status']),  # Queries por tenant + status
    models.Index(fields=['created_at']),  # Ordenação temporal
    models.Index(fields=['external_id']),  # Se tiver (BillingCampaign)
]
```

---

## 🛠️ **SERVICES E UTILS**

### **Services a Criar:**

1. **BillingCampaignService** (`services/billing_campaign_service.py`)
   - Orchestrator principal
   - Valida dados recebidos
   - Enriquece variáveis (calcula dias)
   - Cria Campaign + BillingCampaign + BillingQueue
   - Seleciona variações de template
   - Publica no RabbitMQ

2. **BillingSendService** (`services/billing_send_service.py`)
   - Envia mensagem via EvolutionAPIService
   - Salva no histórico do chat
   - Cria/atualiza Conversation
   - Fecha conversa automaticamente

3. **InstanceChecker** (`services/instance_checker.py`)
   - `InstanceHealthChecker` - Verifica saúde da instância
   - `InstanceRecoveryService` - Trata instância offline/recovery

### **Utils a Criar:**

1. **BillingTemplateEngine** (`utils/template_engine.py`)
   - ✅ NOVO (não reutiliza MessageVariableService)
   - Suporta: `{{variavel}}`, `{{#if}}...{{/if}}`, `{{#unless}}...{{/unless}}`

2. **BillingDateCalculator** (`utils/date_calculator.py`)
   - Calcula dias de atraso/vencimento
   - Enriquece variáveis automaticamente

3. **TemplateSanitizer** (`utils/template_sanitizer.py`)
   - Sanitiza templates (XSS prevention)
   - Valida sintaxe de condicionais

### **Utils a REUTILIZAR:**

- ✅ `apps/contacts/utils.py::normalize_phone` - NÃO criar phone_validator.py

### **Schedulers:**

1. **BillingBusinessHoursScheduler** (`schedulers/business_hours_scheduler.py`)
   - ✅ Wrapper do `BusinessHoursService` existente
   - Métodos: `is_within_business_hours()`, `get_next_valid_datetime()`

---

## 🐰 **RABBITMQ E WORKERS**

### **⚠️ REGRA CRÍTICA: NÃO USAR CELERY!**

Projeto usa **RabbitMQ + aio-pika** para processamento assíncrono.

### **Publisher:**

**Arquivo:** `rabbitmq/billing_publisher.py`

**Queues com Prioridade:**
- `billing.overdue` - Prioridade 10 (alta)
- `billing.upcoming` - Prioridade 5 (média)
- `billing.notification` - Prioridade 1 (baixa)
- `billing.resume` - Retomadas
- `billing.check_stale` - Verificação de queues presas
- `billing.check_recovery` - Verificação de instância

### **Consumer:**

**Arquivo:** `rabbitmq/billing_consumer.py`

**Baseado em:** `apps/campaigns/rabbitmq_consumer.py`

**Adaptações:**
- ✅ Múltiplas queues (6 queues fixas)
- ✅ Prioridades (x-max-priority: 10)
- ✅ Worker sync em thread (não async direto)

### **Worker:**

**Arquivo:** `workers/billing_sender_worker.py`

**Features:**
- ✅ Processa em batches (100 por vez)
- ✅ Throttling configurável (ex: 20 msgs/min)
- ✅ Verifica horário comercial antes de CADA msg
- ✅ Pausa se sair do horário → Retoma automático
- ✅ Verifica instância (health check) antes de enviar
- ✅ Retry em falhas temporárias
- ✅ Health check (heartbeat)
- ✅ Graceful shutdown

### **Management Commands:**

1. **run_billing_consumer** (`management/commands/run_billing_consumer.py`)
   - Roda consumer RabbitMQ
   - Processa queues de billing

2. **run_billing_periodic_tasks** (`management/commands/run_billing_periodic_tasks.py`)
   - Tarefas periódicas (substitui Celery Beat)
   - Verifica queues presas, instância recovery, etc.

---

## 🌐 **APIS E ENDPOINTS**

### **Endpoints a Criar:**

1. **POST** `/api/v1/billing/send/overdue`
   - Envia cobrança atrasada
   - Autenticação: API Key
   - Rate Limiting: Por API Key + IP

2. **POST** `/api/v1/billing/send/upcoming`
   - Envia cobrança a vencer
   - Autenticação: API Key
   - Rate Limiting: Por API Key + IP

3. **POST** `/api/v1/billing/send/notification`
   - Envia notificação/aviso (24/7)
   - Autenticação: API Key
   - Rate Limiting: Por API Key + IP

4. **GET** `/api/v1/billing/queue/{queue_id}/status`
   - Consulta status da fila
   - Retorna progresso, ETA, etc.

5. **POST** `/api/v1/billing/queue/{queue_id}/control`
   - Controla fila (pause/resume/cancel)
   - Ação via body: `{"action": "pause"}`

### **Autenticação:**

**Arquivo:** `authentication.py`

```python
class BillingAPIKeyAuthentication(BaseAuthentication):
    """Autenticação via API Key no header X-Billing-API-Key"""
    pass
```

### **Rate Limiting:**

**Arquivo:** `throttling.py`

**Duas camadas:**
1. Por API Key (config do tenant)
2. Por IP (proteção adicional) - usar `apps/common/rate_limiting.py`

### **Serializers:**

**Arquivo:** `serializers.py`

- `BillingContactSerializer` - Contato individual
- `SendBillingRequestSerializer` - Request de envio
- `SendBillingResponseSerializer` - Response de envio
- `QueueStatusResponseSerializer` - Status da fila

---

## 🔐 **SEGURANÇA E VALIDAÇÃO**

### **Validações Obrigatórias:**

1. **Phone Validation:**
   - ✅ Usar `apps/contacts/utils.py::normalize_phone`
   - ✅ Validar formato E.164

2. **Template Sanitization:**
   - ✅ Remover scripts, iframes, event handlers
   - ✅ Validar sintaxe de condicionais (`{{#if}}` balanceado)

3. **API Key Validation:**
   - ✅ Verificar se está ativa
   - ✅ Verificar expiração
   - ✅ Verificar IP permitido (se configurado)
   - ✅ Verificar tipo de template permitido

4. **Rate Limiting:**
   - ✅ Por API Key (config do tenant)
   - ✅ Por IP (proteção adicional)

5. **Input Validation:**
   - ✅ JSON Schema validation (se configurado no template)
   - ✅ Campos obrigatórios por tipo de template
   - ✅ Validação de data de vencimento

### **Sanitização:**

- ✅ Templates: `TemplateSanitizer.sanitize()`
- ✅ Variáveis: Escapar HTML (se necessário)
- ✅ URLs: Validar protocolos permitidos

---

## ⚡ **PERFORMANCE E OTIMIZAÇÃO**

### **⚠️ REGRAS CRÍTICAS:**

1. **NUNCA fazer N+1 queries:**
   ```python
   # ✅ CORRETO
   contacts = BillingContact.objects.select_related(
       'campaign_contact',
       'template_variation',
       'billing_campaign'
   ).prefetch_related('billing_campaign__tenant')
   
   # ❌ ERRADO
   for contact in contacts:
       print(contact.billing_campaign.tenant.name)  # N+1!
   ```

2. **SEMPRE usar bulk operations:**
   ```python
   # ✅ CORRETO
   BillingContact.objects.bulk_create(contacts, batch_size=500)
   
   # ❌ ERRADO
   for contact in contacts:
       BillingContact.objects.create(...)  # 1000 queries!
   ```

3. **SEMPRE usar SELECT FOR UPDATE no worker:**
   ```python
   # ✅ CORRETO
   contacts = BillingContact.objects.select_for_update(
       skip_locked=True
   ).filter(status='pending')[:100]
   ```

4. **SEMPRE usar iterator() para grandes datasets:**
   ```python
   # ✅ CORRETO
   for contact in BillingContact.objects.filter(...).iterator(chunk_size=1000):
       process(contact)
   ```

5. **SEMPRE cachear business hours no worker:**
   ```python
   # ✅ CORRETO
   self._business_hours_cache = list(
       BusinessHours.objects.filter(tenant=self.tenant, is_active=True)
   )
   ```

### **Indexes Obrigatórios:**

- ✅ `(tenant, status)` - Queries frequentes
- ✅ `(status, scheduled_for)` - Busca de queues prontas
- ✅ `(processing_by, status)` - Busca de queues em processamento
- ✅ `(created_at)` - Ordenação temporal

---

## 🧪 **TESTES E QUALIDADE**

### **Cobertura Mínima:**

- ✅ **80%+ de coverage** em código novo
- ✅ Testes unitários para todos os utils
- ✅ Testes unitários para todos os services
- ✅ Testes de integração para APIs
- ✅ Testes de integração para worker
- ✅ Testes de stress (1000+ mensagens)

### **Arquivos de Teste:**

- `tests/test_models.py` - Models
- `tests/test_services.py` - Services
- `tests/test_utils.py` - Utils (TemplateEngine, DateCalculator, etc.)
- `tests/test_worker.py` - Worker
- `tests/test_api.py` - APIs REST

### **Cenários Críticos a Testar:**

1. ✅ Instância cai no meio do envio
2. ✅ Horário comercial termina durante envio
3. ✅ Rate limit atingido
4. ✅ Template com condicionais complexos
5. ✅ Retry em falhas temporárias
6. ✅ Worker morre (stale queue)
7. ✅ Múltiplas variações de template

---

## ✅ **CHECKLIST DE IMPLEMENTAÇÃO**

### **Fase 1: Setup e Models (2-3 dias)**

- [ ] Criar app `apps/billing`
- [ ] Criar estrutura de pastas completa
- [ ] Criar todos os 6 models
- [ ] Criar migrations
- [ ] Rodar migrations em dev
- [ ] Popular dados de teste (templates padrão)
- [ ] Testar queries (verificar N+1)
- [ ] Criar admin interface (`admin.py`)

### **Fase 2: Utils e Helpers (1-2 dias)**

- [ ] Criar `BillingTemplateEngine` (com condicionais)
- [ ] Criar `BillingDateCalculator`
- [ ] Criar `TemplateSanitizer`
- [ ] Criar `constants.py`
- [ ] Testes unitários para todos os utils
- [ ] Verificar performance dos utils

### **Fase 3: Evolution API Service (1-2 dias)** ← **NOVO!**

**📄 Ver especificação completa:** [EVOLUTION_API_SERVICE_SPEC.md](./EVOLUTION_API_SERVICE_SPEC.md)

- [ ] Criar `apps/common/services/evolution_api_service.py`
- [ ] Implementar `send_text_message()` com retry
- [ ] Implementar `check_health()` (opcional, mas recomendado)
- [ ] Implementar `_normalize_phone()` (reutiliza contacts/utils)
- [ ] Implementar `_make_request()` com retry e backoff
- [ ] Testes unitários
- [ ] Usar em billing desde o início

### **Fase 4: Services (3-4 dias)**

- [ ] Criar `BillingBusinessHoursScheduler` (wrapper)
- [ ] Criar `BillingCampaignService` (orchestrator)
- [ ] Criar `BillingSendService` (usa EvolutionAPIService)
- [ ] Criar `InstanceHealthChecker`
- [ ] Criar `InstanceRecoveryService`
- [ ] Testar cada service isoladamente
- [ ] Testar integração entre services

### **Fase 5: Worker e RabbitMQ (3-4 dias)**

- [ ] Criar `BillingSenderWorker` completo
- [ ] Criar `BillingQueuePublisher` (publica no RabbitMQ)
- [ ] Criar `BillingConsumer` (consome do RabbitMQ)
- [ ] Criar management commands
- [ ] Health check e heartbeat
- [ ] Graceful shutdown
- [ ] Testar worker localmente
- [ ] Testar com RabbitMQ (aio-pika)
- [ ] Testar pausa/retomada
- [ ] Testar instância offline/recovery

### **Fase 6: APIs e Serializers (2-3 dias)**

- [ ] Criar `BillingAPIKeyAuthentication`
- [ ] Criar `BillingAPIRateThrottle`
- [ ] Criar todos os serializers
- [ ] Criar 5 endpoints REST
- [ ] Documentação Swagger
- [ ] Testar com Postman
- [ ] Testar rate limiting

### **Fase 7: Integração com Chat (1-2 dias)**

- [ ] Criar Conversation ao enviar
- [ ] Salvar Message no histórico
- [ ] Fechar conversa automaticamente
- [ ] Testar reabertura se cliente responder
- [ ] Verificar que não quebrou chat existente

### **Fase 8: Testes (2-3 dias)**

- [ ] Testes unitários (>80% coverage)
- [ ] Testes de integração
- [ ] Testes de stress (1000+ mensagens)
- [ ] Testar cenários de falha
- [ ] Testar instância caindo e voltando
- [ ] Testar pausa/retomada por horário

### **Fase 9: Deploy e Monitoramento (1-2 dias)**

- [ ] Deploy em staging
- [ ] Configurar RabbitMQ consumers no Railway
- [ ] Adicionar ao Procfile: `billing_consumer` e `billing_periodic`
- [ ] Configurar monitoramento (logs, métricas)
- [ ] Testar com cliente piloto
- [ ] Ajustar configs (throttling, etc)
- [ ] Deploy em produção

---

## 📝 **PADRÕES DE CÓDIGO**

### **Imports:**

```python
# Ordem:
# 1. Standard library
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

# 2. Django
from django.db import models, transaction
from django.utils import timezone
from django.core.cache import cache

# 3. Third-party
import requests
import aio_pika

# 4. Local apps (reutilização)
from apps.contacts.utils import normalize_phone
from apps.chat.services.business_hours_service import BusinessHoursService
from apps.common.services.evolution_api_service import EvolutionAPIService

# 5. Local billing
from apps.billing.models import BillingQueue, QueueStatus
from apps.billing.constants import BillingConstants
```

### **Logging:**

```python
import logging

logger = logging.getLogger(__name__)

# ✅ CORRETO
logger.info(f"✅ Queue {queue_id} processada")
logger.warning(f"⚠️ Instância {instance_id} offline")
logger.error(f"❌ Erro ao enviar: {e}", exc_info=True)

# ❌ ERRADO
print(f"Debug: {data}")  # NUNCA usar print()
```

### **Error Handling:**

```python
# ✅ CORRETO - Exceções específicas
try:
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
except requests.Timeout:
    logger.warning("Timeout, will retry")
    return retry_later()
except requests.ConnectionError:
    logger.error("Connection failed")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise

# ❌ ERRADO - Bare except
try:
    send_message()
except Exception as e:  # Muito genérico!
    logger.error(f"Error: {e}")
```

### **Type Hints:**

```python
# ✅ SEMPRE usar type hints
def send_message(
    self,
    phone: str,
    message: str,
    retry: bool = True
) -> Tuple[bool, Dict[str, Any]]:
    """..."""
    pass
```

---

## 🚨 **CENÁRIOS CRÍTICOS**

### **1. Instância cai no meio do envio:**

**Comportamento:**
1. Worker detecta instância offline (health check)
2. Pausa queue (`status = INSTANCE_DOWN`)
3. Marca mensagens pending como `pending_retry`
4. Agenda verificação de recuperação (a cada 60s)
5. Quando instância volta, retoma automaticamente

**Código:**
```python
# No worker, antes de CADA envio:
if not self._check_instance_health():
    InstanceRecoveryService.handle_instance_down(
        self.queue,
        "Instância não respondeu ao health check"
    )
    return  # Para processamento
```

### **2. Horário comercial termina durante envio:**

**Comportamento:**
1. Worker verifica horário antes de CADA mensagem
2. Se sair do horário, pausa queue
3. Calcula próximo horário válido
4. Agenda retomada automática
5. Retoma no próximo horário válido

**Código:**
```python
# No worker, antes de CADA mensagem:
if self._should_pause_for_hours():
    self._pause_for_business_hours()
    return  # Para processamento
```

### **3. Worker morre (stale queue):**

**Comportamento:**
1. Task periódica verifica queues com `last_heartbeat` antigo
2. Se heartbeat > 10 minutos, marca como stale
3. Limpa `processing_by`
4. Republica no RabbitMQ para outro worker pegar

**Código:**
```python
# Task periódica (a cada 5 minutos):
stale_threshold = timezone.now() - timedelta(minutes=10)
stale_queues = BillingQueue.objects.filter(
    status=QueueStatus.RUNNING,
    last_heartbeat__lt=stale_threshold
)

for queue in stale_queues:
    queue.processing_by = ''
    queue.save()
    # Republica
    await BillingQueuePublisher.publish_queue(...)
```

---

## 📊 **MÉTRICAS E OBSERVABILIDADE**

### **Prometheus Metrics:**

**Arquivo:** `metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge

# Contador de mensagens
billing_messages_sent_total = Counter(
    'billing_messages_sent_total',
    'Total de mensagens enviadas',
    ['tenant_id', 'template_type', 'status']
)

# Histograma de duração
billing_send_duration_seconds = Histogram(
    'billing_send_duration_seconds',
    'Duração do envio (segundos)',
    ['tenant_id', 'template_type']
)

# Gauge de queues ativas
billing_active_queues = Gauge(
    'billing_active_queues',
    'Número de queues ativas',
    ['tenant_id', 'status']
)
```

### **Structured Logging:**

```python
logger.info(
    "Mensagem enviada",
    extra={
        'billing_campaign_id': str(campaign.id),
        'billing_contact_id': str(contact.id),
        'queue_id': str(queue.id),
        'template_type': template.template_type,
        'instance_id': str(instance.id),
    }
)
```

---

## 🎯 **DECISÕES FINAIS**

### **✅ APROVADO:**

1. ✅ Criar `EvolutionAPIService` centralizado AGORA
2. ✅ Usar em billing desde o início
3. ✅ Migrar campanhas/chat depois (PRs separados)
4. ✅ Reutilizar máximo de código possível
5. ✅ Não usar Celery (RabbitMQ + aio-pika)
6. ✅ Multi-tenant nativo
7. ✅ Segurança primeiro (validação, sanitização, rate limiting)

### **📋 ORDEM DE IMPLEMENTAÇÃO:**

1. EvolutionAPIService (1-2 dias) ← **PRIMEIRO!**
2. Models (2-3 dias)
3. Utils (1-2 dias)
4. Services (3-4 dias)
5. Worker + RabbitMQ (3-4 dias)
6. APIs (2-3 dias)
7. Testes (2-3 dias)
8. Deploy (1-2 dias)

**Total:** 15-20 dias

---

## 📚 **DOCUMENTAÇÃO RELACIONADA**

- [BILLING_SYSTEM_INDEX.md](./BILLING_SYSTEM_INDEX.md) - Índice mestre
- [EVOLUTION_API_SERVICE_SPEC.md](./EVOLUTION_API_SERVICE_SPEC.md) - **Especificação completa do EvolutionAPIService**
- [BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE.md) - Parte 1
- [BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md](./BILLING_SYSTEM_IMPLEMENTATION_GUIDE_PART2.md) - Parte 2
- [BILLING_SYSTEM_REUSE_ANALYSIS.md](./BILLING_SYSTEM_REUSE_ANALYSIS.md) - Análise de reutilização
- [BILLING_SYSTEM_ERRATA.md](./BILLING_SYSTEM_ERRATA.md) - Correções e complementos
- [BILLING_QUICKSTART.md](./BILLING_QUICKSTART.md) - Quick Start
- **[EVOLUTION_API_SERVICE_SPEC.md](./EVOLUTION_API_SERVICE_SPEC.md)** - **Especificação completa do EvolutionAPIService** ⭐

---

## ✅ **CHECKLIST RÁPIDO ANTES DE COMMIT**

- [ ] Nenhum `print()` no código?
- [ ] Queries otimizadas (select_related/prefetch_related)?
- [ ] Bulk operations ao invés de loops?
- [ ] Transactions em operações críticas?
- [ ] Exception handling específico?
- [ ] Rate limiting em endpoints públicos?
- [ ] Logging estruturado?
- [ ] Type hints em todas as funções?
- [ ] Testes criados?
- [ ] Documentação atualizada?

---

**🎯 Use este arquivo como referência durante TODO o desenvolvimento!**

**Última atualização:** Dezembro 2025

