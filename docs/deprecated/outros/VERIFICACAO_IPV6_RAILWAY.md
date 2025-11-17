# 🌐 **VERIFICAÇÃO IPv6 - RAILWAY + EVOLUTION API**

## 🔍 **PROBLEMA IDENTIFICADO:**

- **Railway:** Apenas IPv6
- **Evolution API:** Apenas IPv4
- **Resultado:** Webhooks não chegam (incompatibilidade de protocolo)

## 🚀 **SOLUÇÃO APLICADA:**

Configurar **IPv6 na Evolution API** para comunicação com Railway.

---

## 🧪 **TESTES PARA FAZER APÓS CONFIGURAR IPv6:**

### **1. Teste de Conectividade:**
```bash
# Teste se Evolution API consegue acessar Railway
curl -6 https://alreasense-backend-production.up.railway.app/api/health/
```

### **2. Teste do Webhook:**
```bash
# Simula webhook da Evolution API
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"event":"test.webhook","instance":"test","data":{"test":true}}' \
  https://alreasense-backend-production.up.railway.app/webhooks/evolution/
```

### **3. Verificar Logs Railway:**
Procurar por:
```
✅ Webhook allowed: IP XXXX:XXXX:XXXX:XXXX matches allowed origins
📥 Webhook received: a1b2c3d4_e5f6g7h8 - messages.upsert
💾 Evento armazenado no cache: a1b2c3d4_e5f6g7h8
```

---

## 🎯 **CONFIGURAÇÕES EVOLUTION API:**

### **URL do Webhook:**
```
https://alreasense-backend-production.up.railway.app/webhooks/evolution/
```

### **Eventos a Ativar:**
- `messages.upsert` - Novas mensagens
- `messages.update` - Status de mensagens (entregue, lida)
- `connection.update` - Status da conexão
- `contacts.update` - Atualizações de contatos
- `presence.update` - Status de presença

### **Configurações Importantes:**
- ✅ **webhook_base64:** true
- ✅ **webhookByEvents:** true
- ✅ **reject_call:** true
- ✅ **always_online:** true

---

## 📊 **MONITORAMENTO:**

### **1. Logs Railway:**
- Acesse dashboard Railway
- Vá em **Deployments** → Seu serviço
- **View Logs** → Filtre por "webhook"

### **2. Página de Monitoramento:**
- Acesse `/admin/webhook-monitoring`
- Veja eventos em tempo real
- Verifique estatísticas do cache

### **3. Teste Manual:**
- Envie mensagem via WhatsApp
- Verifique se aparece nos logs
- Confirme no monitoramento

---

## 🎉 **RESULTADO ESPERADO:**

Após configurar IPv6 na Evolution API:

1. **Webhooks chegam** no Railway
2. **Logs aparecem** com eventos
3. **Monitoramento funciona** em tempo real
4. **Campanhas processam** status de entrega
5. **Sistema completo** funcionando

---

## 🔧 **SE AINDA NÃO FUNCIONAR:**

### **Verificações Adicionais:**
1. **Firewall:** Verificar se porta 443 está aberta
2. **DNS:** Confirmar resolução IPv6
3. **Certificado SSL:** Verificar se está válido
4. **CORS:** Confirmar configuração
5. **Headers:** Verificar se Evolution API envia headers corretos

### **Debug Avançado:**
```bash
# Teste de conectividade IPv6
ping6 alreasense-backend-production.up.railway.app

# Teste de DNS
nslookup -type=AAAA alreasense-backend-production.up.railway.app

# Teste de porta
telnet alreasense-backend-production.up.railway.app 443
```

---

## 📝 **NOTA IMPORTANTE:**

O problema era **protocolo de rede**, não código! 🎯

Com IPv6 configurado na Evolution API, tudo deve funcionar perfeitamente.

**Aguardo o resultado da configuração IPv6!** 🚀
