# 🔔 **CONFIGURAÇÃO WEBHOOK GLOBAL - EVOLUTION API**

## 🌐 **URL DO WEBHOOK:**

```
https://SEU-DOMINIO-BACKEND-RAILWAY.up.railway.app/api/connections/webhooks/evolution/
```

---

## 📍 **COMO PEGAR O DOMÍNIO DO RAILWAY:**

### **Opção 1: No Dashboard Railway**
1. Acesse https://railway.app
2. Entre no projeto "ALREA Sense"
3. Clique no serviço **"Backend"** (Django)
4. Aba **"Settings"**
5. Seção **"Networking"**
6. Copie o **"Public Domain"**
7. Exemplo: `alrea-sense-production.up.railway.app`

### **Opção 2: Verificar variável de ambiente**
```bash
# No Railway, variável RAILWAY_PUBLIC_DOMAIN
echo $RAILWAY_PUBLIC_DOMAIN
```

---

## 🔧 **CONFIGURAR WEBHOOK GLOBAL NA EVOLUTION API:**

### **Via API (Recomendado):**

```bash
curl -X POST 'https://sua-evolution-api.com/webhook/settings/global' \
  -H 'Content-Type: application/json' \
  -H 'apikey: SUA_API_KEY' \
  -d '{
    "url": "https://SEU-DOMINIO-RAILWAY.up.railway.app/api/connections/webhooks/evolution/",
    "enabled": true,
    "webhook_by_events": true,
    "webhook_base64": true,
    "events": [
      "messages.upsert",
      "messages.update",
      "connection.update",
      "presence.update",
      "contacts.upsert",
      "contacts.update",
      "chats.upsert",
      "chats.update",
      "chats.delete",
      "messages.delete"
    ]
  }'
```

---

### **Via Interface Evolution API (se tiver):**

```
1. Acesse painel da Evolution API
2. Configurações → Webhooks
3. Webhook Global:
   ✅ Habilitar: ON
   📍 URL: https://SEU-DOMINIO-RAILWAY.up.railway.app/api/connections/webhooks/evolution/
   ✅ Webhook By Events: ON
   ✅ Webhook Base64: ON
   
4. Eventos (selecionar todos):
   ✅ messages.upsert
   ✅ messages.update
   ✅ connection.update
   ✅ presence.update
   ✅ contacts.upsert
   ✅ contacts.update
   ✅ chats.upsert
   ✅ chats.update
   ✅ chats.delete
   ✅ messages.delete
```

---

## 📊 **EVENTOS QUE O BACKEND PROCESSA:**

### **✅ Implementados (prontos):**
```python
# backend/apps/connections/webhook_views.py

✅ messages.upsert     → Mensagens novas (recebidas e enviadas)
⚠️ messages.update     → Status de mensagens (delivered, read) - TODO
⚠️ connection.update   → Status da conexão (conectado, desconectado) - TODO
⚠️ presence.update     → Presença (online, offline) - TODO
```

### **❌ Não implementados (ignorados):**
```
❌ contacts.upsert     → Novos contatos
❌ contacts.update     → Atualização de contatos
❌ chats.upsert        → Novas conversas
❌ chats.update        → Atualização de conversas
❌ chats.delete        → Conversas deletadas
❌ messages.delete     → Mensagens deletadas
```

---

## 🧪 **COMO TESTAR O WEBHOOK:**

### **1. Verificar se o endpoint está no ar:**

```bash
curl https://SEU-DOMINIO-RAILWAY.up.railway.app/api/health/
```

**Resposta esperada:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-13T...",
  ...
}
```

---

### **2. Testar webhook manualmente:**

```bash
curl -X POST 'https://SEU-DOMINIO-RAILWAY.up.railway.app/api/connections/webhooks/evolution/' \
  -H 'Content-Type: application/json' \
  -d '{
    "event": "messages.upsert",
    "data": {
      "instance": "test-instance",
      "messages": [{
        "key": {
          "remoteJid": "5511999999999@s.whatsapp.net",
          "fromMe": false,
          "id": "TEST123"
        },
        "message": {
          "messageType": "conversation",
          "conversation": "Mensagem de teste"
        },
        "messageTimestamp": 1697200000
      }]
    }
  }'
```

**Resposta esperada:**
```json
{
  "status": "success",
  "processed": 1
}
```

---

### **3. Verificar logs no Railway:**

```bash
# No Railway:
# 1. Vai no serviço Backend
# 2. Aba "Deployments"
# 3. Clique no deployment ativo
# 4. Aba "Logs"
# 5. Procure por:
```

**Logs esperados:**
```
✅ Webhook received: {...}
✅ Processing message: TEST123
✅ Message processed successfully
```

---

### **4. Enviar mensagem real no WhatsApp:**

```
1. Configure o webhook global
2. Envie uma mensagem para um número conectado na Evolution API
3. Verifique os logs do Railway
4. Deve aparecer:
   ✅ Webhook received: {"event": "messages.upsert", ...}
   ✅ Processing message...
```

---

## 📝 **ESTRUTURA DO PAYLOAD (messages.upsert):**

```json
{
  "event": "messages.upsert",
  "data": {
    "instance": "nome-da-instancia",
    "messages": [
      {
        "key": {
          "remoteJid": "5511999999999@s.whatsapp.net",
          "fromMe": false,
          "id": "3EB0XXXXX"
        },
        "message": {
          "messageType": "conversation",
          "conversation": "Texto da mensagem"
        },
        "messageTimestamp": 1697200000,
        "pushName": "Nome do Contato"
      }
    ]
  }
}
```

---

## 🔥 **PRÓXIMOS PASSOS (Para Amanhã):**

### **1. Implementar `messages.update` (Status de Entrega):**
```python
def handle_message_update(self, data):
    """
    Atualizar status de mensagens de campanha:
    - sent (enviada)
    - delivered (entregue)
    - read (lida)
    - failed (falhou)
    """
    # Buscar CampaignContact pelo whatsapp_message_id
    # Atualizar status e timestamps (delivered_at, read_at)
```

**Usa caso:** Tracking de entregas das campanhas

---

### **2. Implementar `connection.update` (Status da Instância):**
```python
def handle_connection_update(self, data):
    """
    Atualizar status da instância WhatsApp:
    - open (conectada)
    - close (desconectada)
    """
    # Buscar WhatsAppInstance pelo nome
    # Atualizar connection_state
```

**Usa caso:** Monitorar health das instâncias

---

### **3. Salvar respostas de campanhas:**
```python
def handle_message_upsert(self, data):
    """
    Além de salvar mensagem, verificar se é resposta de campanha:
    1. Buscar CampaignContact pelo phone
    2. Se encontrar, salvar em CampaignReply
    3. Notificar usuário
    """
```

**Usa caso:** Ver quem respondeu as campanhas

---

## ⚠️ **IMPORTANTE - SEGURANÇA:**

### **Recomendação para Produção:**

Adicionar autenticação ao webhook:

```python
# backend/apps/connections/webhook_views.py

def post(self, request):
    # Verificar token de segurança
    auth_token = request.headers.get('X-Webhook-Token')
    expected_token = settings.EVOLUTION_WEBHOOK_SECRET
    
    if auth_token != expected_token:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    # ... resto do código
```

**Configurar na Evolution API:**
```bash
curl -X POST 'https://sua-evolution-api.com/webhook/settings/global' \
  -H 'apikey: SUA_API_KEY' \
  -d '{
    "url": "https://SEU-DOMINIO-RAILWAY.up.railway.app/api/connections/webhooks/evolution/",
    "webhook_by_events": true,
    "webhook_base64": true,
    "headers": {
      "X-Webhook-Token": "seu-token-secreto-aqui"
    }
  }'
```

---

## 📊 **RESUMO:**

```
┌────────────────────────────────────────────┐
│  WEBHOOK EVOLUTION API - SETUP             │
├────────────────────────────────────────────┤
│  1. URL: https://SEU-DOMINIO-RAILWAY       │
│           .up.railway.app                  │
│           /api/connections/webhooks        │
│           /evolution/                      │
│                                            │
│  2. Eventos implementados:                 │
│     ✅ messages.upsert (mensagens)         │
│     ⏳ messages.update (status)            │
│     ⏳ connection.update (instância)       │
│                                            │
│  3. Teste:                                 │
│     - curl no endpoint                     │
│     - Enviar mensagem real                 │
│     - Verificar logs Railway               │
│                                            │
│  4. Amanhã:                                │
│     - Implementar messages.update          │
│     - Implementar connection.update        │
│     - Salvar respostas de campanhas        │
└────────────────────────────────────────────┘
```

---

**📄 Criado: `WEBHOOK_EVOLUTION_SETUP.md`**

