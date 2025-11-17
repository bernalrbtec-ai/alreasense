# 🎯 WEBHOOK FOCADO NO ALREA FLOW (Campanhas)

## 📋 **DECISÃO: FLOW PRIMEIRO, SENSE DEPOIS**

Excelente priorização! O Flow é mais crítico para o negócio.

---

## 🚀 **ALREA FLOW - O QUE PRECISA DO WEBHOOK:**

### **Objetivo do Flow:**
Enviar campanhas de WhatsApp e **rastrear entregas** para:
- ✅ Saber se mensagem foi enviada
- ✅ Saber se foi entregue
- ✅ Saber se foi lida
- ✅ Saber se falhou
- ✅ Detectar opt-out (respostas "SAIR", "PARAR")
- ✅ Atualizar health score das instâncias

---

## 📡 **EVENTOS ESSENCIAIS PARA O FLOW:**

### **1️⃣ messages.update** ⭐ CRÍTICO
**Por quê:** Atualiza status da mensagem (enviada → entregue → lida)

**Payload:**
```json
{
  "event": "messages.update",
  "instance": "tenant_1_inst_1",
  "data": {
    "key": {
      "remoteJid": "5511999999999@s.whatsapp.net",
      "id": "3EB0B431E4B3..."  ← ID da mensagem
    },
    "update": {
      "status": 3  ← 1=sent, 2=delivered, 3=read
    }
  }
}
```

**O que fazer:**
```python
# Buscar CampaignContact pelo whatsapp_message_id
campaign_contact = CampaignContact.objects.get(
    whatsapp_message_id=message_id
)

# Atualizar status conforme update
if status == 2:  # Delivered
    campaign_contact.status = 'delivered'
    campaign_contact.delivered_at = timezone.now()
    campaign_contact.save()
    
    # Atualizar instância (health)
    instance.record_message_delivered()
    
    # Log
    CampaignLog.log_message_delivered(...)
    
elif status == 3:  # Read
    campaign_contact.status = 'read'
    campaign_contact.read_at = timezone.now()
    campaign_contact.save()
    
    # Atualizar instância (health)
    instance.record_message_read()
    
    # Log
    CampaignLog.log_message_read(...)
```

---

### **2️⃣ messages.upsert** ⭐ IMPORTANTE
**Por quê:** Recebe respostas dos contatos (detectar opt-out, engajamento)

**Payload:**
```json
{
  "event": "messages.upsert",
  "instance": "tenant_1_inst_1",
  "data": {
    "messages": [{
      "key": {
        "remoteJid": "5511999999999@s.whatsapp.net",
        "fromMe": false  ← Mensagem recebida (não enviada)
      },
      "message": {
        "conversation": "SAIR"  ← Opt-out!
      }
    }]
  }
}
```

**O que fazer:**
```python
# Se mensagem é RECEBIDA (fromMe = false):
if not from_me:
    text = message['conversation'].upper()
    phone = remote_jid.split('@')[0]
    
    # Detectar opt-out
    if text in ['SAIR', 'PARAR', 'CANCELAR', 'STOP']:
        # Buscar contato
        contact = Contact.objects.get(phone=phone, tenant=tenant)
        
        # Marcar opt-out (LGPD)
        contact.mark_opted_out()
        
        # Se estava em campanha, marcar como opt-out
        CampaignContact.objects.filter(
            contact=contact,
            status='pending'
        ).update(status='opted_out')
        
        # Log
        CampaignLog.objects.create(
            log_type='contact_opted_out',
            message=f'{contact.name} solicitou opt-out',
            ...
        )
    
    # Registrar resposta (engajamento)
    contact.last_interaction_date = timezone.now()
    contact.total_messages_received += 1
    contact.save()
```

---

### **3️⃣ connection.update** ⭐ IMPORTANTE
**Por quê:** Saber se instância desconectou durante campanha

**Payload:**
```json
{
  "event": "connection.update",
  "instance": "tenant_1_inst_1",
  "data": {
    "state": "close"  ← ou "open"
  }
}
```

**O que fazer:**
```python
# Atualizar estado da instância
instance.connection_state = state

if state == 'close':
    instance.status = 'inactive'
    
    # Pausar campanhas ativas nesta instância
    Campaign.objects.filter(
        instances=instance,
        status='active'
    ).update(is_paused=True)
    
    # Log
    CampaignLog.objects.create(
        log_type='instance_disconnected',
        message=f'Instância {instance.friendly_name} desconectou',
        severity='critical',
        ...
    )

instance.save()
```

---

### **4️⃣ messages.delete** 🟡 OPCIONAL
**Por quê:** Saber se contato deletou mensagem (analytics)

**Uso:** Métricas de engajamento

---

### **5️⃣ presence.update** 🟡 OPCIONAL (PARA DEPOIS)
**Por quê:** Saber quando contato está online (otimizar horário)

**Uso:** Machine learning para melhor horário de envio

---

## 🧠 **ALREA SENSE - DEIXAR PARA DEPOIS:**

### **Eventos do Sense (Análise IA):**
- ⏳ messages.upsert (conversas completas)
- ⏳ chats.upsert (contexto de conversas)
- ⏳ contacts.upsert (atualizar base)

**Por quê deixar depois:**
- Sense faz análise de conversas (não é crítico para Flow)
- Flow precisa funcionar independente do Sense
- Pode implementar Sense quando Flow estiver estável

---

## 📊 **PRIORIZAÇÃO DE EVENTOS (Flow):**

| Evento | Prioridade | Implementar | Uso no Flow |
|--------|-----------|-------------|-------------|
| **messages.update** | 🔴 CRÍTICA | ✅ Agora | Rastrear entrega/leitura |
| **messages.upsert** | 🟠 ALTA | ✅ Agora | Detectar opt-out, respostas |
| **connection.update** | 🟠 ALTA | ✅ Agora | Pausar se desconectar |
| **messages.delete** | 🟡 MÉDIA | ⏳ Depois | Analytics |
| **presence.update** | 🟢 BAIXA | ⏳ Depois | Otimização de horário |
| **contacts.upsert** | 🟢 BAIXA | ⏳ Sense | Auto-atualizar base |
| **chats.upsert** | 🟢 BAIXA | ⏳ Sense | Contexto de conversas |

---

## 🔄 **FLUXO COMPLETO DO FLOW (Webhook):**

```
┌────────────────────────────────────────────────────────┐
│  CAMPANHA ENVIANDO MENSAGENS                          │
├────────────────────────────────────────────────────────┤
│  Celery Task → send_campaign_messages()              │
│    ↓                                                   │
│  Para cada contato:                                   │
│    1. Envia mensagem via Evolution                    │
│    2. Recebe message_id                               │
│    3. Salva CampaignContact:                          │
│       - whatsapp_message_id = message_id ← CHAVE     │
│       - status = 'sent'                               │
│       - sent_at = now()                               │
└────────────────────────────────────────────────────────┘
                        ↓
                   ⏰ Alguns segundos/minutos...
                        ↓
┌────────────────────────────────────────────────────────┐
│  WEBHOOK RECEBE UPDATE                                 │
├────────────────────────────────────────────────────────┤
│  POST /api/webhooks/evolution/                        │
│  {                                                     │
│    "event": "messages.update",                        │
│    "instance": "tenant_1_inst_1",                     │
│    "data": {                                           │
│      "key": {                                          │
│        "id": "3EB0B431..."  ← Mesmo ID!               │
│      },                                                │
│      "update": {                                       │
│        "status": 2  ← Entregue!                       │
│      }                                                 │
│    }                                                   │
│  }                                                     │
└────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────┐
│  PROCESSAR UPDATE (Webhook Handler)                   │
├────────────────────────────────────────────────────────┤
│  1. message_id = data['key']['id']                    │
│  2. status = data['update']['status']                 │
│                                                        │
│  3. Buscar no banco:                                  │
│     campaign_contact = CampaignContact.objects.get(   │
│         whatsapp_message_id=message_id                │
│     )                                                  │
│     # ✅ Encontrou!                                   │
│                                                        │
│  4. Atualizar:                                        │
│     if status == 2:  # Delivered                      │
│         campaign_contact.status = 'delivered'         │
│         campaign_contact.delivered_at = now()         │
│         campaign_contact.save()                       │
│                                                        │
│     if status == 3:  # Read                           │
│         campaign_contact.status = 'read'              │
│         campaign_contact.read_at = now()              │
│         campaign_contact.save()                       │
│                                                        │
│  5. Atualizar métricas da campanha:                  │
│     campaign.delivered_count += 1                     │
│     campaign.save()                                    │
│                                                        │
│  6. Atualizar health da instância:                    │
│     instance.record_message_delivered()               │
│     # Aumenta health_score                            │
│                                                        │
│  7. Criar log:                                        │
│     CampaignLog.log_message_delivered(...)            │
│                                                        │
│  8. WebSocket → Frontend (tempo real)                 │
│     ws.send('campaign_updated', {...})                │
└────────────────────────────────────────────────────────┘
```

---

## 🗄️ **RELACIONAMENTO DE DADOS (Chave):**

```
Webhook → message_id
   ↓ SELECT
CampaignContact (whatsapp_message_id = message_id)
   ↓ FK
├─ Campaign (atualizar contadores)
├─ Contact (atualizar engajamento)
├─ WhatsAppInstance (atualizar health)
└─ CampaignLog (criar log)
```

**Chave de cruzamento:** `whatsapp_message_id`

---

## 📊 **DADOS ATUALIZADOS POR WEBHOOK:**

### **Na tabela CampaignContact:**
```python
# Enviamos (Celery task):
whatsapp_message_id = "3EB0B431..."  # ← Salva ID
status = 'sent'
sent_at = '2024-11-10 14:30:00'

# Webhook atualiza (messages.update status=2):
status = 'delivered'  # ← Atualiza
delivered_at = '2024-11-10 14:30:15'  # +15 segundos

# Webhook atualiza (messages.update status=3):
status = 'read'  # ← Atualiza
read_at = '2024-11-10 14:32:00'  # +2 minutos
```

### **Na tabela Campaign (Agregado):**
```python
# Atualizado a cada webhook:
sent_count = 150
delivered_count = 148  # +1 a cada delivered
read_count = 89        # +1 a cada read
failed_count = 2       # +1 a cada failed

# Calculado:
delivery_rate = (148 / 150) * 100  # 98.7%
read_rate = (89 / 148) * 100       # 60.1%
```

### **Na tabela WhatsAppInstance (Health):**
```python
# Atualizado a cada webhook:
msgs_delivered_today = 148  # +1 a cada delivered
msgs_read_today = 89        # +1 a cada read
msgs_failed_today = 2       # +1 a cada failed
health_score = 95           # Aumenta com sucesso, diminui com falha
```

---

## 🎯 **EVENTOS PRIORIZADOS PARA FLOW:**

### **FASE 1: Essencial (Implementar Agora)** ✅

```python
WEBHOOK_EVENTS_FLOW_MVP = [
    'messages.update',      # ⭐ Status: sent → delivered → read
    'messages.upsert',      # ⭐ Respostas (opt-out)
    'connection.update',    # ⭐ Instância desconectou
]
```

**Com esses 3 eventos, o Flow funciona 100%!**

### **FASE 2: Melhorias (Depois)** ⏳

```python
WEBHOOK_EVENTS_FLOW_ENHANCED = [
    'messages.delete',      # Analytics (contato deletou)
    'presence.update',      # Otimizar horário
]
```

### **FASE 3: Sense (Muito Depois)** 🧠

```python
WEBHOOK_EVENTS_SENSE = [
    'messages.upsert',      # Conversas completas (análise IA)
    'chats.upsert',         # Contexto de conversas
    'contacts.upsert',      # Auto-atualizar base
    'chats.update',         # Mudanças em conversas
]
```

---

## 🔧 **IMPLEMENTAÇÃO PRIORIZADA:**

### **Webhook Handler (Simplified for Flow):**

```python
# backend/apps/campaigns/webhook_handler.py (novo arquivo)

@csrf_exempt
def campaign_webhook(request):
    """
    Webhook handler focado em campanhas (Flow).
    Processa apenas eventos essenciais para rastreamento.
    """
    
    data = json.loads(request.body)
    event = data.get('event')
    instance_name = data.get('instance')
    
    # Buscar instância
    instance = WhatsAppInstance.objects.get(instance_name=instance_name)
    tenant = instance.tenant
    
    # Roteamento simplificado
    if event == 'messages.update':
        return handle_message_status_update(data, instance, tenant)
    
    elif event == 'messages.upsert':
        # Só processar se fromMe = false (resposta do contato)
        if not data.get('data', {}).get('key', {}).get('fromMe'):
            return handle_contact_reply(data, instance, tenant)
    
    elif event == 'connection.update':
        return handle_connection_change(data, instance)
    
    else:
        # Ignorar outros eventos (Sense processará depois)
        return JsonResponse({'status': 'ignored'})


def handle_message_status_update(data, instance, tenant):
    """Atualiza status de mensagem da campanha (sent → delivered → read)."""
    
    message_id = data['data']['key']['id']
    status_code = data['data']['update']['status']
    
    # Buscar CampaignContact
    try:
        cc = CampaignContact.objects.select_related('campaign', 'contact').get(
            whatsapp_message_id=message_id
        )
    except CampaignContact.DoesNotExist:
        # Mensagem não é de campanha (pode ser do Sense)
        return JsonResponse({'status': 'not_campaign'})
    
    # Atualizar conforme status
    if status_code == 2:  # Delivered
        cc.status = 'delivered'
        cc.delivered_at = timezone.now()
        cc.save()
        
        # Atualizar contadores
        cc.campaign.delivered_count += 1
        cc.campaign.save()
        
        # Health da instância
        instance.record_message_delivered()
        
        # Log
        CampaignLog.log_message_delivered(cc.campaign, instance, cc.contact, cc)
        
    elif status_code == 3:  # Read
        cc.status = 'read'
        cc.read_at = timezone.now()
        cc.save()
        
        # Atualizar contadores
        cc.campaign.read_count += 1
        cc.campaign.save()
        
        # Health da instância
        instance.record_message_read()
        
        # Log
        CampaignLog.log_message_read(cc.campaign, instance, cc.contact, cc)
    
    return JsonResponse({'status': 'updated'})


def handle_contact_reply(data, instance, tenant):
    """Processa resposta do contato (opt-out, engajamento)."""
    
    phone = data['data']['key']['remoteJid'].split('@')[0]
    text = data['data']['message'].get('conversation', '').upper()
    
    # Buscar contato
    try:
        contact = Contact.objects.get(phone=phone, tenant=tenant)
    except Contact.DoesNotExist:
        return JsonResponse({'status': 'contact_not_found'})
    
    # Detectar opt-out
    OPT_OUT_KEYWORDS = ['SAIR', 'PARAR', 'CANCELAR', 'STOP', 'REMOVER', 'NAO QUERO']
    
    if text in OPT_OUT_KEYWORDS:
        # Marcar opt-out
        contact.mark_opted_out()
        
        # Remover de campanhas ativas
        CampaignContact.objects.filter(
            contact=contact,
            status__in=['pending', 'sent']
        ).update(status='opted_out')
        
        # Log em TODAS campanhas afetadas
        for cc in CampaignContact.objects.filter(contact=contact, status='opted_out'):
            CampaignLog.objects.create(
                campaign=cc.campaign,
                log_type='contact_opted_out',
                severity='warning',
                message=f'{contact.name} solicitou opt-out',
                contact=contact,
                details={'keyword': text}
            )
    
    # Atualizar engajamento
    contact.last_interaction_date = timezone.now()
    contact.total_messages_received += 1
    contact.save()
    
    return JsonResponse({'status': 'processed'})
```

---

## 📋 **ESTRUTURA DE ARQUIVOS (Proposta):**

```
backend/
├── apps/
│   ├── campaigns/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── tasks.py (Celery - envio)
│   │   ├── webhook_handler.py ← NOVO! (Flow)
│   │   └── services.py
│   │
│   ├── notifications/
│   │   ├── models.py (WhatsAppInstance)
│   │   └── views.py
│   │
│   └── connections/
│       ├── webhook_views.py ← Existe (genérico)
│       └── ...
│
└── alrea_sense/
    └── urls.py:
        path('api/webhooks/evolution/', ...) ← Redirecionar
```

---

## 🎯 **CHECKLIST DE IMPLEMENTAÇÃO (Flow):**

### **Backend:**
- [ ] Criar `campaigns/webhook_handler.py`
- [ ] Função `handle_message_status_update()` (delivered/read)
- [ ] Função `handle_contact_reply()` (opt-out)
- [ ] Função `handle_connection_change()` (desconexão)
- [ ] Atualizar `CampaignContact.status`
- [ ] Atualizar `Campaign` contadores
- [ ] Atualizar `WhatsAppInstance` health
- [ ] Criar `CampaignLog` para cada evento
- [ ] Endpoint: `/api/webhooks/flow/` ou reutilizar `/evolution/`

### **Testes:**
- [ ] Enviar mensagem de campanha
- [ ] Webhook atualiza para 'delivered'
- [ ] Webhook atualiza para 'read'
- [ ] Contato responde "SAIR" → opt-out automático
- [ ] Instância desconecta → campanha pausa

---

## ⚡ **PERFORMANCE:**

### **Webhook Handler DEVE SER RÁPIDO (<100ms):**

```python
# ✅ FAZER (Rápido):
1. Parse JSON (5ms)
2. Buscar CampaignContact (SELECT, 10ms)
3. UPDATE status (20ms)
4. Retornar 200 (5ms)

Total: ~40ms ✅

# ❌ NÃO FAZER (Lento):
1. Análise IA (1-3 segundos) ← Celery!
2. Gerar embedding (500ms) ← Celery!
3. Queries complexas (100ms+) ← Otimizar!
4. Chamadas externas ← Celery!
```

**Regra:** Webhook responde rápido, processamento pesado vai para Celery.

---

## 📊 **RESUMO EXECUTIVO:**

```
┌─────────────────────────────────────────────────────┐
│  WEBHOOK PARA FLOW - RESUMO                         │
├─────────────────────────────────────────────────────┤
│  OBJETIVO:                                           │
│  Rastrear status de mensagens de campanhas          │
│                                                      │
│  EVENTOS ESSENCIAIS (3):                             │
│  1. messages.update → Delivered/Read                │
│  2. messages.upsert → Opt-out, respostas            │
│  3. connection.update → Desconexão                   │
│                                                      │
│  FLUXO:                                              │
│  Envia → Salva message_id                           │
│  Webhook → Busca message_id                          │
│  Atualiza → Status + Timestamps                      │
│  Métricas → Campaign + Instance                      │
│                                                      │
│  NÃO FAZER AGORA:                                    │
│  ❌ Análise IA (Sense)                              │
│  ❌ Busca semântica                                  │
│  ❌ Embeddings                                       │
│                                                      │
│  FAZER DEPOIS (Quando Flow estiver OK):              │
│  ⏳ Sense (IA, conversas)                           │
└─────────────────────────────────────────────────────┘
```

---

**📄 Criei `WEBHOOK_FLOW_PRIORIZADO.md` com análise completa focada no Flow!**

**✅ Foco 100% no rastreamento de campanhas, deixando Sense para depois!**



