# 🧪 **GUIA COMPLETO - TESTAR WEBHOOK EVOLUTION API**

## 🌐 **SUA URL DO WEBHOOK:**

```
https://alreasense-backend-production.up.railway.app/api/connections/webhooks/evolution/
```

---

## ✅ **TESTE 1: VERIFICAR SE O BACKEND ESTÁ NO AR**

### **Via navegador:**
```
https://alreasense-backend-production.up.railway.app/api/health/
```

### **Via PowerShell:**
```powershell
curl https://alreasense-backend-production.up.railway.app/api/health/
```

### **Resposta esperada:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-13T...",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "celery": "healthy"
  }
}
```

**✅ Se retornou JSON = Backend está funcionando!**

---

## ✅ **TESTE 2: TESTAR WEBHOOK MANUALMENTE**

### **PowerShell (Windows):**

```powershell
$body = @{
    event = "messages.upsert"
    data = @{
        instance = "test-instance"
        messages = @(
            @{
                key = @{
                    remoteJid = "5511999999999@s.whatsapp.net"
                    fromMe = $false
                    id = "TEST123"
                }
                message = @{
                    messageType = "conversation"
                    conversation = "Mensagem de teste do webhook"
                }
                messageTimestamp = 1697200000
                pushName = "Teste Usuario"
            }
        )
    }
} | ConvertTo-Json -Depth 10

$headers = @{
    "Content-Type" = "application/json"
}

Invoke-WebRequest `
    -Uri "https://alreasense-backend-production.up.railway.app/api/connections/webhooks/evolution/" `
    -Method POST `
    -Headers $headers `
    -Body $body
```

### **Resposta esperada:**
```
StatusCode        : 200
StatusDescription : OK
Content           : {"status":"success","processed":1}
```

**✅ Se retornou status 200 = Webhook está funcionando!**

---

## ✅ **TESTE 3: VERIFICAR LOGS NO RAILWAY**

### **Como acessar:**
1. Acesse https://railway.app
2. Entre no projeto "ALREA Sense"
3. Clique no serviço **"Backend"**
4. Clique na aba **"Deployments"**
5. Clique no deployment ativo (o primeiro da lista)
6. Clique na aba **"Logs"**

### **O que procurar nos logs:**

```
✅ Webhook received: {"event": "messages.upsert", ...}
✅ Processing message: TEST123
✅ Message processed successfully
```

**Se aparecer esses logs = Webhook processou a mensagem!**

---

## ✅ **TESTE 4: CONFIGURAR NA EVOLUTION API**

### **Opção A: Via API (Recomendado)**

#### **PowerShell:**
```powershell
$body = @{
    url = "https://alreasense-backend-production.up.railway.app/api/connections/webhooks/evolution/"
    enabled = $true
    webhook_by_events = $true
    webhook_base64 = $true
    events = @(
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
    )
} | ConvertTo-Json -Depth 10

$headers = @{
    "Content-Type" = "application/json"
    "apikey" = "SUA_API_KEY_EVOLUTION"
}

Invoke-WebRequest `
    -Uri "https://sua-evolution-api.com/webhook/settings/global" `
    -Method POST `
    -Headers $headers `
    -Body $body
```

**Substitua:**
- `sua-evolution-api.com` → URL da sua Evolution API
- `SUA_API_KEY_EVOLUTION` → API Key da Evolution

---

### **Opção B: Via Painel Evolution (se tiver interface)**

```
1. Acesse o painel da Evolution API
2. Configurações → Webhooks → Global Webhook
3. Preencha:
   ✅ URL: https://alreasense-backend-production.up.railway.app/api/connections/webhooks/evolution/
   ✅ Enabled: ON
   ✅ Webhook By Events: ON
   ✅ Webhook Base64: ON
   
4. Selecione TODOS os eventos:
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

5. Clique em "Salvar"
```

---

## ✅ **TESTE 5: ENVIAR MENSAGEM REAL NO WHATSAPP**

### **Passo a passo:**

1. **Conecte uma instância na Evolution API**
   - Use QR Code para conectar um número de teste

2. **Envie uma mensagem para esse número**
   - De outro WhatsApp, envie: "Teste webhook"

3. **Verifique os logs do Railway**
   - Backend → Deployments → [Ativo] → Logs
   - Procure por:
     ```
     Webhook received: {"event": "messages.upsert", ...}
     Processing message: ...
     Message processed successfully
     ```

4. **Verifique no banco de dados**
   - A mensagem deve ter sido salva na tabela `messages_message`

**✅ Se aparecer nos logs = Webhook está funcionando com mensagens reais!**

---

## 🔍 **TROUBLESHOOTING (Se não funcionar):**

### **1. Backend não responde:**
```powershell
# Teste o health check
curl https://alreasense-backend-production.up.railway.app/api/health/
```

**Se der erro:**
- Verifique se o backend está rodando no Railway
- Verifique os logs para erros de deploy

---

### **2. Webhook retorna erro 404:**
```
Status: 404 Not Found
```

**Solução:**
- Verifique se a URL está EXATAMENTE assim:
  ```
  /api/connections/webhooks/evolution/
  ```
- Tem que ter a barra no final: `/`

---

### **3. Webhook retorna erro 500:**
```
Status: 500 Internal Server Error
```

**Solução:**
- Vá nos logs do Railway
- Procure por erros Python/Django
- Me manda o erro que eu ajudo!

---

### **4. Evolution API não envia eventos:**

**Verifique:**
- ✅ Webhook está `enabled: true`?
- ✅ URL está correta (com https://)?
- ✅ Eventos estão selecionados?
- ✅ `webhook_by_events: true`?

**Teste manual:**
```powershell
# Enviar evento de teste direto pro webhook
$body = '{"event":"messages.upsert","data":{"instance":"test","messages":[{"key":{"id":"TEST"}}]}}' 

Invoke-WebRequest `
    -Uri "https://alreasense-backend-production.up.railway.app/api/connections/webhooks/evolution/" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"
```

---

## 📊 **ESTRUTURA DO PAYLOAD (messages.upsert):**

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

## 📋 **CHECKLIST DE TESTE:**

```
[ ] 1. Health check retorna 200 OK
[ ] 2. Webhook manual retorna {"status":"success"}
[ ] 3. Logs do Railway mostram "Webhook received"
[ ] 4. Evolution API configurada com webhook global
[ ] 5. Mensagem real do WhatsApp aparece nos logs
[ ] 6. Mensagem salva no banco de dados
```

**✅ Se todos passaram = WEBHOOK FUNCIONANDO 100%!**

---

## 🎯 **RESUMO RÁPIDO:**

### **URL do Webhook:**
```
https://alreasense-backend-production.up.railway.app/api/connections/webhooks/evolution/
```

### **Teste rápido:**
```powershell
curl -X POST `
  "https://alreasense-backend-production.up.railway.app/api/connections/webhooks/evolution/" `
  -H "Content-Type: application/json" `
  -d '{"event":"messages.upsert","data":{"instance":"test","messages":[{"key":{"id":"TEST"}}]}}'
```

### **Configurar Evolution:**
```
URL: https://alreasense-backend-production.up.railway.app/api/connections/webhooks/evolution/
Enabled: ON
Events: Todos
```

### **Ver logs:**
```
Railway → Backend → Deployments → [Ativo] → Logs
```

---

## 💡 **PRÓXIMOS PASSOS (AMANHÃ):**

1. ✅ Webhook funcionando
2. ⏳ Implementar `messages.update` (status de entrega)
3. ⏳ Implementar `connection.update` (status da instância)
4. ⏳ Salvar respostas de campanhas
5. ⏳ Notificar usuário sobre respostas

---

**📄 Criado: `TESTE_WEBHOOK_COMPLETO.md`**
**🌐 Seu webhook: https://alreasense-backend-production.up.railway.app/api/connections/webhooks/evolution/**

