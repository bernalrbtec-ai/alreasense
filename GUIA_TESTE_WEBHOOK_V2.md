# 🧪 GUIA DE TESTE: Webhook Evolution API v2.3.4

## ✅ **SUA VERSÃO SUPORTA WEBHOOK COMPLETO**

Evolution API **v2.3.4** tem suporte total a:
- ✅ Endpoint `/webhook/set/{instance}`
- ✅ Parâmetro `webhookBase64`
- ✅ Parâmetro `webhookByEvents`
- ✅ Array de `events`

---

## 🧪 **TESTE PARA FAZER AGORA**

### **Passo 1: Criar uma nova instância no sistema**

```
1. Acesse: Configurações → Instâncias WhatsApp
2. Clique "Nova Instância"
3. Nome: "Teste Webhook v2"
4. Clique "Criar Instância"
5. Clique "Gerar QR Code"
```

### **Passo 2: Verificar logs no Railway/Docker**

```bash
# Se estiver em Railway:
railway logs --tail 100

# Se estiver em Docker local:
docker logs alrea_sense_backend_local --tail 100

# Procure por:
🔧 CONFIGURANDO WEBHOOK VIA /webhook/set
📍 URL: https://...
📊 Eventos: 10
📡 Status Code: ???
```

### **Passo 3: Verificar o que os logs mostram**

#### **Cenário A: Sucesso ✅**
```
   🔧 CONFIGURANDO WEBHOOK VIA /webhook/set
   📍 URL: https://evo.rbtec.com.br/webhook/set/tenant_123_inst_1
   📊 Eventos: 10
   📡 Status Code: 200
   ✅ WEBHOOK CONFIGURADO COM SUCESSO!
```
**Ação:** ✅ Funcionou! Verificar no painel Evolution

#### **Cenário B: Erro 404**
```
   🔧 CONFIGURANDO WEBHOOK VIA /webhook/set
   📍 URL: https://evo.rbtec.com.br/webhook/set/tenant_123_inst_1
   📡 Status Code: 404
   ❌ ERRO: Status 404
```
**Ação:** ⚠️ Endpoint não encontrado (problema de URL ou versão)

#### **Cenário C: Erro 401/403**
```
   📡 Status Code: 401
   ❌ ERRO: Status 401
   Unauthorized
```
**Ação:** ⚠️ API Key não tem permissão

#### **Cenário D: Erro 400**
```
   📡 Status Code: 400
   ❌ ERRO: Status 400
   Body: {"error": "Invalid format..."}
```
**Ação:** ⚠️ Formato JSON incorreto

---

## 🔍 **SE OS LOGS MOSTRAREM ERRO, TESTAR MANUALMENTE**

### **Teste Manual no Postman/Insomnia:**

```bash
POST https://evo.rbtec.com.br/webhook/set/nome_da_sua_instancia

Headers:
  apikey: SUA_API_KEY_MASTER
  Content-Type: application/json

Body (RAW JSON):
{
  "enabled": true,
  "url": "https://seu-app.up.railway.app/api/notifications/webhook/",
  "webhookByEvents": false,
  "webhookBase64": true,
  "events": [
    "messages.upsert",
    "messages.update",
    "connection.update"
  ]
}
```

**Resposta esperada (200/201):**
```json
{
  "webhook": {
    "instanceName": "nome_da_sua_instancia",
    "webhook": {
      "url": "https://...",
      "events": [...],
      "enabled": true,
      "webhookBase64": true
    }
  }
}
```

---

## 🎯 **VERIFICAÇÃO NO PAINEL EVOLUTION**

### **Caminho:**
```
1. Acesse painel Evolution: https://evo.rbtec.com.br
2. Login com sua API Key Master
3. Vá em "Instâncias"
4. Selecione sua instância
5. Clique em "Webhook" ou "Configurações"
```

### **O que verificar:**
```
✅ Webhook Enabled: [ ✓ ] (checkbox marcado)
✅ Webhook URL: https://seu-app.up.railway.app/api/notifications/webhook/
✅ Webhook Base64: [ ✓ ] (checkbox marcado)
✅ Events (checkboxes):
   [ ✓ ] messages.upsert
   [ ✓ ] messages.update
   [ ✓ ] messages.delete
   [ ✓ ] connection.update
   [ ✓ ] presence.update
   [ ✓ ] contacts.upsert
   [ ✓ ] contacts.update
   [ ✓ ] chats.upsert
   [ ✓ ] chats.update
   [ ✓ ] chats.delete
```

---

## 💡 **POSSÍVEIS PROBLEMAS E SOLUÇÕES**

### **Problema 1: BASE_URL vazio**
```python
# Se BASE_URL não está configurado:
'url': '/api/notifications/webhook/'  # ← URL incompleta!

# Solução:
# Verificar variável de ambiente BASE_URL no Railway
BASE_URL=https://seu-app.up.railway.app
```

### **Problema 2: API Key errada**
```python
# Se usar API key da instância ao invés da Master:
apikey: instance.api_key  # ← Pode não ter permissão

# Solução:
# Sempre usar API Master (system_api_key)
```

### **Problema 3: Nome da instância com caracteres especiais**
```python
# Se instance_name tem espaços ou caracteres especiais:
instance_name = "teste webhook"  # ← Pode dar erro

# Solução:
# Usar URL encoding ou validar nome
from urllib.parse import quote
webhook_url = f"{api_url}/webhook/set/{quote(self.instance_name)}"
```

---

## 🚀 **AÇÃO IMEDIATA**

**Faça isso agora:**

1. **Crie uma nova instância** (se ainda não criou)
2. **Verifique os logs** no Railway/Docker
3. **Me envie o log** que aparecer (especialmente as linhas com 🔧 e 📡)

Com o log vou saber exatamente qual o problema!

---

## 📋 **EXEMPLO DE LOG ESPERADO**

```
🆕 Criando nova instância no Evolution: tenant_1_inst_2
📋 Resposta criar instância: {...}
✅ API key específica capturada: B6VK-S4-P0AE7Z6U-54...
🔧 Configurando webhook completo...
   🔧 CONFIGURANDO WEBHOOK VIA /webhook/set
   📍 URL: https://evo.rbtec.com.br/webhook/set/tenant_1_inst_2
   🔑 API Key: whatsapp-orchestrator...
   🌐 Webhook URL: https://alreasense.up.railway.app/api/notifications/webhook/
   📊 Eventos: 10
   📷 Base64: True
   📡 Status Code: 200  ← SUCESSO!
   📋 Response: {"webhook":{"instanceName":"tenant_1_inst_2"...}}
   ✅ WEBHOOK CONFIGURADO COM SUCESSO!
```

---

**📊 Crie uma instância agora e me mostre os logs! Vou identificar o problema!**



