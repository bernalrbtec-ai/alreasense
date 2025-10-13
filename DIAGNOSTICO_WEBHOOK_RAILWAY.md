# 🔧 **DIAGNÓSTICO: WEBHOOKS NÃO CHEGAM NO RAILWAY**

## 🚨 **PROBLEMA IDENTIFICADO:**

**URL do webhook estava INCORRETA!**

### ❌ **ANTES (ERRADO):**
```
https://alreasense-backend-production.up.railway.app/api/webhooks/evolution/
```

### ✅ **DEPOIS (CORRETO):**
```
https://alreasense-backend-production.up.railway.app/webhooks/evolution/
```

---

## 🔍 **CORREÇÕES APLICADAS:**

### **1. Backend (`views.py`):**
```python
# ANTES ❌
webhook_url = f"{request.scheme}://{request.get_host()}/api/webhooks/evolution/"

# DEPOIS ✅  
webhook_url = f"{request.scheme}://{request.get_host()}/webhooks/evolution/"
```

### **2. Frontend (`EvolutionConfigPage.tsx`):**
```typescript
// ANTES ❌
webhook_url: `${window.location.origin}/api/webhooks/evolution/`,

// DEPOIS ✅
webhook_url: `${window.location.origin}/webhooks/evolution/`,
```

### **3. Endpoint de Teste Criado:**
```
GET/POST /api/connections/webhooks/test/
```

---

## 🧪 **COMO TESTAR:**

### **1. Teste Manual do Endpoint:**
```bash
# Teste GET
curl -H "Authorization: Bearer SEU_TOKEN" \
  https://alreasense-backend-production.up.railway.app/api/connections/webhooks/test/

# Teste POST (simula webhook)
curl -X POST -H "Authorization: Bearer SEU_TOKEN" \
  https://alreasense-backend-production.up.railway.app/api/connections/webhooks/test/
```

### **2. Teste Direto do Webhook:**
```bash
# Simula webhook da Evolution API
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"event":"test.webhook","instance":"test","data":{"test":true}}' \
  https://alreasense-backend-production.up.railway.app/webhooks/evolution/
```

### **3. Verificar Logs:**
```bash
# No Railway, procure por:
📥 Webhook received
✅ Webhook allowed
💾 Evento armazenado no cache
```

---

## 🎯 **URLS CORRETAS PARA EVOLUTION API:**

### **Webhook URL:**
```
https://alreasense-backend-production.up.railway.app/webhooks/evolution/
```

### **Eventos a Configurar:**
```json
{
  "events": [
    "messages.upsert",
    "messages.update", 
    "messages.delete",
    "connection.update",
    "presence.update",
    "contacts.upsert",
    "contacts.update",
    "chats.upsert",
    "chats.update",
    "chats.delete"
  ],
  "webhook_url": "https://alreasense-backend-production.up.railway.app/webhooks/evolution/",
  "webhook_base64": true
}
```

---

## 🔧 **PRÓXIMOS PASSOS:**

### **1. Fazer Deploy:**
```bash
git add .
git commit -m "fix: Corrigir URL do webhook - remover /api/ prefix"
git push
```

### **2. Reconfigurar Evolution API:**
1. Acesse sua Evolution API
2. Vá em **Webhooks**
3. Configure a URL correta:
   ```
   https://alreasense-backend-production.up.railway.app/webhooks/evolution/
   ```
4. Ative os eventos necessários
5. Salve a configuração

### **3. Testar:**
1. Envie uma mensagem de teste
2. Verifique os logs do Railway
3. Acesse `/admin/webhook-monitoring` para ver eventos

---

## 🎉 **RESULTADO ESPERADO:**

Após as correções, você deve ver nos logs:

```
🔒 Webhook security config: ALLOW_ALL_ORIGINS_IN_DEV=False
🔒 Allowed webhook origins: ['evo.rbtec.com.br']
✅ Webhook allowed: IP X.X.X.X matches allowed origins
📥 Webhook received: a1b2c3d4_e5f6g7h8 - messages.upsert
💾 Evento armazenado no cache: a1b2c3d4_e5f6g7h8
```

**O problema estava na URL incorreta!** 🎯
