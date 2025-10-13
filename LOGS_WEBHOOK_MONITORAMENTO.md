# 📋 **LOGS DE MONITORAMENTO DE WEBHOOKS**

## 🔍 **SIM, OS EVENTOS APARECEM NO LOG!**

Todos os eventos webhook são logados detalhadamente. Aqui está o que você verá nos logs:

---

## 🚀 **1. LOGS DE INICIALIZAÇÃO**

```
🔒 Webhook security config: ALLOW_ALL_ORIGINS_IN_DEV=False
🔒 Allowed webhook origins: ['evo.rbtec.com.br']
```

---

## 📥 **2. LOGS DE RECEPÇÃO DE WEBHOOKS**

### **✅ Webhook Permitido:**
```
✅ Webhook allowed: IP 192.168.1.100 matches allowed origins
```

### **📥 Webhook Recebido:**
```
📥 Webhook received: a1b2c3d4_e5f6g7h8 - messages.upsert
💾 Evento armazenado no cache: a1b2c3d4_e5f6g7h8
```

### **🚫 Webhook Bloqueado:**
```
🚫 Webhook blocked: IP 192.168.1.200 not in allowed origins
```

---

## 📊 **3. LOGS DE PROCESSAMENTO POR TIPO DE EVENTO**

### **📞 Contatos:**
```
📞 Contacts update received: {
  "event": "contacts.update",
  "instance": "instancia_01",
  "data": {...}
}
📞 Contact updated - Instance: instancia_01, JID: 5511999999999@s.whatsapp.net, Name: João Silva
```

### **💬 Mensagens:**
```
📥 New message created: 123 from 5511999999999@s.whatsapp.net
Message update: msg_123 status=delivered
Message msg_123 marked as delivered
```

### **🏃‍♂️ Status de Campanha:**
```
Campaign contact 456 marked as delivered
Campaign 789 stats: 15/100 delivered, 8 read, 2 failed
```

### **🔗 Conexão:**
```
Connection update received: {"event": "connection.update", "instance": "instancia_01", "data": {...}}
```

### **👤 Presença:**
```
Presence update received: {"event": "presence.update", "instance": "instancia_01", "data": {...}}
```

---

## 📦 **4. LOGS DO CACHE REDIS**

### **✅ Armazenamento:**
```
📦 Evento armazenado no cache: a1b2c3d4_e5f6g7h8
```

### **❌ Erros de Cache:**
```
❌ Erro ao armazenar evento no cache: Connection refused
❌ Erro ao recuperar evento do cache: Key not found
```

### **🔄 Reprocessamento:**
```
🔄 Reprocessamento concluído: {'total': 50, 'processed': 48, 'errors': 2, 'by_type': {'messages.upsert': 30, 'messages.update': 18}}
```

---

## 🎯 **5. LOGS DE EVENTOS ESPECÍFICOS**

### **Mensagens Deletadas:**
```
🗑️ Message deleted: messages.delete
```

### **Mensagens Editadas:**
```
✏️ Message edited: messages.edited
```

### **Contatos Criados:**
```
📞 Contact upsert: contacts.upsert
```

### **Chats Atualizados:**
```
💬 Chat updated: chats.update
💬 Chat upsert: chats.upsert
💬 Chat deleted: chats.delete
```

### **Grupos:**
```
👥 Group upsert: groups.upsert
👥 Group updated: groups.update
👥 Group participants updated: groups.participants.update
```

### **Mensagens Enviadas:**
```
📤 Message sent: send.message
```

---

## 🔧 **6. LOGS DE ERROS**

### **JSON Inválido:**
```
Invalid JSON in webhook payload
```

### **Erro Geral:**
```
Webhook error: Connection timeout
Error handling message update: Database connection failed
```

### **Evento Não Tratado:**
```
Unhandled event type: custom.event
```

---

## 📈 **7. COMO MONITORAR OS LOGS**

### **No Railway:**
1. Acesse o **dashboard do Railway**
2. Vá em **Deployments** → Seu serviço
3. Clique em **View Logs**
4. Filtre por **"webhook"** ou **"📥"**

### **No Terminal Local:**
```bash
# Ver logs em tempo real
docker-compose logs -f backend | grep -E "(📥|📞|💬|🔗|👤|📦)"

# Ver logs específicos de webhook
docker-compose logs backend | grep "Webhook"
```

### **Filtros Úteis:**
```bash
# Apenas eventos recebidos
grep "📥 Webhook received"

# Apenas erros
grep "❌\|Error"

# Apenas eventos de contatos
grep "📞"

# Apenas eventos de mensagens
grep "💬\|📥"
```

---

## 🎯 **RESUMO**

**SIM, TODOS OS EVENTOS APARECEM NO LOG!** Você verá:

1. **✅ Confirmação de recebimento** de cada webhook
2. **📦 Armazenamento no cache** Redis
3. **📊 Processamento detalhado** por tipo de evento
4. **🏃‍♂️ Atualizações de campanha** em tempo real
5. **❌ Erros e problemas** quando ocorrem
6. **🔄 Estatísticas** de reprocessamento

Os logs são **muito detalhados** e incluem **emojis** para facilitar a identificação visual! 🎉
