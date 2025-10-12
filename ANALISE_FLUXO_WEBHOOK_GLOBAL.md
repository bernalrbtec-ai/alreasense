# 🔄 ANÁLISE: Fluxo de Processamento de Webhook Global

## 🎯 **SUA PERGUNTA:**

> "Como o sistema vai tratar essas entradas? Vai salvar todas e depois cruzar os dados?"

---

## 📡 **PAYLOAD QUE CHEGA DO EVOLUTION (Webhook Global):**

```json
{
  "event": "messages.upsert",
  "instance": "tenant_1_inst_1",        ← IDENTIFICADOR DA INSTÂNCIA
  "data": {
    "key": {
      "remoteJid": "5511999999999@s.whatsapp.net",
      "fromMe": false,
      "id": "3EB0B431E4B3B12B5F53"
    },
    "message": {
      "conversation": "Olá, gostaria de saber sobre..."
    },
    "messageTimestamp": 1699999999,
    "pushName": "João Silva"
  },
  "server_url": "https://evo.rbtec.com.br",
  "apikey": "B6VK-S4..."
}
```

**Informações cruciais:**
- ✅ `instance`: Nome da instância que recebeu a mensagem
- ✅ `event`: Tipo de evento (messages.upsert, connection.update, etc)
- ✅ `data`: Dados do evento (mensagem, contato, etc)

---

## 🔄 **FLUXO DE PROCESSAMENTO (Como Funciona):**

### **Passo 1: Webhook Recebe Evento** 📥

```python
# backend/apps/connections/webhook_views.py - Linha 24-50

POST /api/webhooks/evolution/

def post(self, request):
    data = json.loads(request.body)
    
    # Identificar tipo de evento
    event_type = data.get('event')  # Ex: "messages.upsert"
    
    # Rotear para handler correto
    if event_type == 'messages.upsert':
        return self.handle_message_upsert(data)
    elif event_type == 'messages.update':
        return self.handle_message_update(data)
    # ...
```

**Resposta:** ✅ Identifica tipo de evento e roteia

---

### **Passo 2: Identificar Instância** 🔍

```python
# Linha 52-66

def handle_message_upsert(self, data):
    # Extrair nome da instância do payload
    instance_name = data.get('instance')  # ← CHAVE!
    
    # Extrair mensagens
    messages = data.get('data', {}).get('messages', [])
```

**Resposta:** ✅ Payload traz nome da instância

---

### **Passo 3: Cruzar com Banco de Dados** 🗄️

```python
# Linha 67-121 (lógica atual precisa melhorar)

# ❌ PROBLEMA ATUAL: Busca tenant genérico
tenant = Tenant.objects.first()  # ← ERRADO para multi-tenant!

# ✅ DEVERIA SER:
from apps.notifications.models import WhatsAppInstance

# 1. Buscar instância pelo nome
instance = WhatsAppInstance.objects.get(
    instance_name=instance_name  # ← "tenant_1_inst_1"
)

# 2. Pegar o tenant da instância
tenant = instance.tenant

# 3. Processar mensagem com tenant correto
message = Message.objects.create(
    tenant=tenant,              # ← Tenant correto!
    instance=instance,          # ← Instância correta!
    chat_id=chat_id,
    text=text_content,
    ...
)
```

**Resposta:** 
- ⚠️ **Atualmente:** Salva com tenant genérico (ERRADO)
- ✅ **Deveria:** Buscar instância → pegar tenant → salvar (CORRETO)

---

### **Passo 4: Processar Dados** ⚙️

```python
# Linha 124-149

# Salvar mensagem no banco
message_obj, created = Message.objects.get_or_create(
    chat_id=chat_id,
    message_id=message_id,
    defaults={
        'tenant': tenant,           # ← Do passo 3
        'text': text_content,
        'sender': sender,
        'created_at': timestamp,
        # Campos IA (preenchidos depois)
        'sentiment': None,
        'emotion': None,
        'satisfaction': None,
    }
)

# Se mensagem nova, disparar análise IA
if created:
    trigger_ai_analysis(message_obj)  # ← Celery task
```

**Resposta:** ✅ Salva primeiro, processa depois (assíncrono)

---

## 📊 **ESTRATÉGIAS DE PROCESSAMENTO:**

### **Estratégia A: Salvar Tudo Depois Cruzar** 🔴 NÃO RECOMENDADO
```python
# 1. Salvar evento bruto em RawWebhookEvent
raw_event = RawWebhookEvent.objects.create(
    payload=data,
    received_at=timezone.now()
)

# 2. Celery task processa depois
process_webhook_event.delay(raw_event.id)

# 3. Na task: buscar instância, cruzar, criar Message
```

**Problemas:**
- ❌ Duplica dados (payload + Message)
- ❌ Mais lento (2 escritas)
- ❌ Mais complexo
- ⚠️ Útil só para auditoria/debug

### **Estratégia B: Processar na Hora** 🟢 RECOMENDADO (ATUAL)
```python
# 1. Recebe webhook
data = json.loads(request.body)

# 2. Identifica instância IMEDIATAMENTE
instance_name = data.get('instance')
instance = WhatsAppInstance.objects.get(instance_name=instance_name)

# 3. Pega tenant da instância
tenant = instance.tenant

# 4. Cria Message JÁ com tenant correto
message = Message.objects.create(
    tenant=tenant,
    instance=instance,
    ...
)

# 5. Celery task assíncrona para IA (não bloqueia)
analyze_message_async.delay(message.id)
```

**Vantagens:**
- ✅ Mais rápido (1 escrita)
- ✅ Tenant correto desde o início
- ✅ Menos duplicação
- ✅ Mais simples

### **Estratégia C: Híbrido** 🟡 PARA CASOS COMPLEXOS
```python
# 1. Validar e salvar mínimo (síncrono)
message = Message.objects.create(
    tenant=tenant,
    text=text,
    processed=False  # ← Flag
)

# 2. Processar dados complexos (assíncrono)
enrich_message.delay(message.id)
  → Buscar contato
  → Atualizar engajamento
  → Gerar embedding
  → Análise IA
  → processed=True
```

**Quando usar:**
- ⚠️ Processamento muito pesado
- ⚠️ Integrações externas
- ⚠️ Múltiplas etapas

---

## 🎯 **FLUXO COMPLETO RECOMENDADO (Webhook Global):**

```
┌──────────────────────────────────────────────────────┐
│  1. EVOLUTION API (Webhook Global Ativo)             │
├──────────────────────────────────────────────────────┤
│  Instância recebe mensagem                           │
│    ↓                                                  │
│  Envia para webhook global:                          │
│  POST https://seu-app/api/webhooks/evolution/        │
│  {                                                    │
│    "instance": "tenant_1_inst_1",  ← IDENTIFICADOR   │
│    "event": "messages.upsert",                       │
│    "data": {...}                                      │
│  }                                                    │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│  2. ALREA SENSE - Webhook Endpoint                   │
│  /api/webhooks/evolution/                            │
├──────────────────────────────────────────────────────┤
│  def post(request):                                  │
│    data = json.loads(request.body)                   │
│    instance_name = data.get('instance')              │
│                                                       │
│    # 🔍 BUSCAR INSTÂNCIA NO BANCO                    │
│    instance = WhatsAppInstance.objects.get(          │
│        instance_name=instance_name                   │
│    )                                                  │
│    # ✅ Instância encontrada!                        │
│    # ✅ Tenant identificado: instance.tenant         │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│  3. PROCESSAR EVENTO (Síncrono - Rápido)            │
├──────────────────────────────────────────────────────┤
│  if event == 'messages.upsert':                      │
│    # Criar mensagem NO BANCO IMEDIATAMENTE           │
│    message = Message.objects.create(                 │
│        tenant=instance.tenant,  ← Tenant correto!    │
│        instance=instance,                            │
│        text=data['text'],                            │
│        chat_id=data['chat_id'],                      │
│        # IA fields null por enquanto                 │
│        sentiment=None,                               │
│        emotion=None,                                  │
│    )                                                  │
│    # ✅ Mensagem salva com tenant correto            │
│                                                       │
│  elif event == 'connection.update':                  │
│    # Atualizar status da instância                   │
│    instance.connection_state = data['state']         │
│    instance.save()                                    │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│  4. PROCESSAR ASSÍNCRONO (Celery - Pesado)          │
├──────────────────────────────────────────────────────┤
│  # Disparar tasks Celery (não bloqueia webhook)     │
│                                                       │
│  analyze_message_async.delay(                        │
│      tenant_id=tenant.id,                            │
│      message_id=message.id                           │
│  )                                                    │
│    ↓                                                  │
│  Task Celery:                                        │
│    → Chamar IA (sentiment, emotion)                  │
│    → Gerar embedding (pgvector)                      │
│    → Atualizar Message com resultados                │
│    → Enviar WebSocket para frontend                  │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│  5. FRONTEND ATUALIZA (WebSocket Real-Time)         │
├──────────────────────────────────────────────────────┤
│  Usuário vê:                                         │
│  • Nova mensagem aparece na lista                    │
│  • Análise IA preenchida (após alguns segundos)      │
│  • Badge de sentimento atualizado                    │
└──────────────────────────────────────────────────────┘
```

---

## ✅ **RESPOSTA À SUA PERGUNTA:**

### **"Vai salvar todas e depois cruzar os dados?"**

**Não exatamente.** O fluxo é:

1. **Recebe webhook** (Evolution → Sense)
2. **Identifica instância IMEDIATAMENTE** pelo campo `instance` do payload
3. **Busca no banco** `WhatsAppInstance.objects.get(instance_name=...)`
4. **Pega tenant** da instância encontrada
5. **Salva Message JÁ com tenant correto** (1 escrita, dados corretos)
6. **Dispara processamento assíncrono** (IA, embedding) via Celery

**Não salva tudo primeiro!** Identifica e cruza **na hora**, salva **já correto**.

---

## 🗄️ **DADOS SALVOS:**

### **Imediato (Webhook Handler - Síncrono):**
```python
Message.objects.create(
    tenant=tenant,              # ✅ Já identificado
    instance=instance,          # ✅ Já identificado
    chat_id="...",              # ✅ Do payload
    text="...",                 # ✅ Do payload
    sender="...",               # ✅ Do payload
    created_at=timestamp,       # ✅ Do payload
    # Campos IA vazios por enquanto:
    sentiment=None,
    emotion=None,
    satisfaction=None,
)
```

**Tempo:** ~50-100ms  
**Resposta ao Evolution:** 200 OK (rápido!)

### **Assíncrono (Celery Task - Pode demorar):**
```python
# Task processa em background
analyze_message_async.delay(message.id)

# Dentro da task:
  → Chamar API de IA (500ms-2s)
  → Gerar embedding (100-200ms)
  → Atualizar Message:
      message.sentiment = 0.72
      message.emotion = 'positivo'
      message.satisfaction = 85
      message.save()
  → Enviar WebSocket para frontend
```

**Tempo:** 1-3 segundos  
**Não bloqueia webhook!**

---

## 🔍 **IDENTIFICAÇÃO DE TENANT (Crucial!):**

### **Problema Atual (BUG):**
```python
# Linha 102 de webhook_views.py
tenant = Tenant.objects.first()  # ❌ ERRADO!
```

**Problema:**
- Pega **sempre o primeiro tenant** do banco
- Se tem tenant_1, tenant_2, tenant_3 → sempre usa tenant_1
- **Todos os dados vão para o tenant errado!** 🚨

### **Solução Correta:**
```python
# 1. Extrair nome da instância do payload
instance_name = data.get('instance')  # "tenant_2_inst_1"

# 2. Buscar instância no banco
from apps.notifications.models import WhatsAppInstance

instance = WhatsAppInstance.objects.select_related('tenant').get(
    instance_name=instance_name
)

# 3. Pegar tenant correto
tenant = instance.tenant  # ✅ tenant_2 (correto!)

# 4. Salvar com tenant certo
message = Message.objects.create(
    tenant=tenant,  # ✅ Correto!
    ...
)
```

**Como funciona:**
- Instância tem nome único: `tenant_2_inst_1`
- Banco tem mapeamento: `tenant_2_inst_1` → Instância ID → Tenant ID
- 1 query SQL: `SELECT * FROM whatsapp_instances WHERE instance_name = 'tenant_2_inst_1'`
- ✅ Tenant identificado corretamente!

---

## 📊 **FLUXO DE DADOS (Diagrama Completo):**

```
Evolution API (Global Webhook)
        │
        │ POST {instance: "tenant_2_inst_1", event: "...", data: {...}}
        ▼
┌─────────────────────────────────────────────────────┐
│  ALREA SENSE - Webhook Handler                      │
│  /api/webhooks/evolution/                            │
├─────────────────────────────────────────────────────┤
│  1. Parse JSON                                      │
│  2. instance_name = data['instance']                │
└─────────────────────────────────────────────────────┘
        │
        │ SELECT * FROM whatsapp_instances WHERE instance_name = ?
        ▼
┌─────────────────────────────────────────────────────┐
│  BANCO DE DADOS (PostgreSQL)                        │
├─────────────────────────────────────────────────────┤
│  whatsapp_instances:                                │
│  ┌──────────────────────────────────────────────┐  │
│  │ id │ instance_name     │ tenant_id │ ...   │  │
│  ├────┼───────────────────┼───────────┼────────┤  │
│  │ 1  │ tenant_1_inst_1   │ uuid_1    │ ...   │  │
│  │ 2  │ tenant_2_inst_1   │ uuid_2    │ ...   │ ← Encontra
│  │ 3  │ tenant_3_inst_1   │ uuid_3    │ ...   │  │
│  └────┴───────────────────┴───────────┴────────┘  │
│                                                     │
│  Retorna: instance = {id:2, tenant_id: uuid_2}     │
└─────────────────────────────────────────────────────┘
        │
        │ tenant = instance.tenant
        ▼
┌─────────────────────────────────────────────────────┐
│  PROCESSAMENTO COM TENANT CORRETO                   │
├─────────────────────────────────────────────────────┤
│  INSERT INTO messages (                             │
│    tenant_id = uuid_2,        ← CORRETO!            │
│    instance_id = 2,                                  │
│    chat_id = "...",                                  │
│    text = "...",                                     │
│    sentiment = NULL,          ← Preenchido depois    │
│    ...                                               │
│  )                                                   │
│                                                      │
│  Retorna HTTP 200 (rápido, <100ms)                  │
└─────────────────────────────────────────────────────┘
        │
        │ Celery.delay(message_id)
        ▼
┌─────────────────────────────────────────────────────┐
│  CELERY TASK (Assíncrono - Pode demorar)           │
├─────────────────────────────────────────────────────┤
│  1. Chamar IA para análise (1-3s)                   │
│  2. Gerar embedding (100ms)                          │
│  3. UPDATE messages SET                              │
│       sentiment = 0.72,                              │
│       emotion = 'positivo',                          │
│       satisfaction = 85                              │
│     WHERE id = ?                                     │
│                                                      │
│  4. WebSocket → Frontend (atualização real-time)    │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 **ESTRATÉGIA RECOMENDADA:**

### **NÃO salvar tudo e depois cruzar. Fazer:**

```
✅ 1. Receber webhook
✅ 2. Identificar instância (pelo nome do payload)
✅ 3. Buscar no banco (1 query)
✅ 4. Pegar tenant da instância
✅ 5. Salvar JÁ com dados corretos (1 INSERT)
✅ 6. Disparar processamento pesado em background
```

**Por quê?**
- ✅ Mais rápido (webhook não fica bloqueado)
- ✅ Tenant correto desde o início
- ✅ Menos queries
- ✅ Menos duplicação
- ✅ Evolution API recebe 200 OK rápido

---

## ⚠️ **BUG ATUAL QUE PRECISA CORRIGIR:**

**Arquivo:** `backend/apps/connections/webhook_views.py`  
**Linha:** 102

**Antes (ERRADO):**
```python
tenant = Tenant.objects.first()  # ❌ Sempre o primeiro!
```

**Depois (CORRETO):**
```python
# Buscar instância pelo nome
from apps.notifications.models import WhatsAppInstance

instance = WhatsAppInstance.objects.select_related('tenant').get(
    instance_name=instance_name
)
tenant = instance.tenant  # ✅ Tenant correto!
```

---

## 📋 **RESUMO FINAL:**

```
┌─────────────────────────────────────────────────────┐
│  ESTRATÉGIA DE PROCESSAMENTO                        │
├─────────────────────────────────────────────────────┤
│  ❌ NÃO: Salvar tudo → depois cruzar               │
│  ✅ SIM: Identificar → cruzar → salvar correto     │
│                                                      │
│  FLUXO:                                              │
│  1. Webhook chega (50ms)                            │
│  2. Busca instância no banco (10ms)                 │
│  3. Identifica tenant (0ms - já tem)                │
│  4. Salva Message com tenant correto (30ms)         │
│  5. Retorna 200 OK (total: ~100ms)                  │
│  6. Celery processa pesado em background (1-3s)     │
│                                                      │
│  VANTAGEM:                                           │
│  ✅ Rápido para Evolution                           │
│  ✅ Dados corretos desde início                     │
│  ✅ Multi-tenant funcionando                         │
└─────────────────────────────────────────────────────┘
```

---

**💡 RESPOSTA: Não salva tudo e depois cruza. Identifica tenant NA HORA (pelo nome da instância) e salva JÁ com dados corretos. Processamento pesado (IA) vai para Celery assíncrono!**



