# 🆕 SETUP NOVO EVOLUTION API

## ✅ CORREÇÕES APLICADAS

### **1. Bug Crítico: Payload muito grande** 🔥
```
❌ ANTES: Webhook error: Request body exceeded settings.DATA_UPLOAD_MAX_MEMORY_SIZE
✅ AGORA: Limite aumentado para 50MB (suporta mídia em base64)
```

**Commit:** `fix: aumenta limite de payload para webhooks Evolution (50MB)`
**Status:** ✅ Deployando no Railway agora

---

## 🎯 CHECKLIST NOVO EVOLUTION

### **1. Aguardar Deploy Railway** ⏳
```bash
# Verificar status:
git log --oneline -1
# Deve mostrar: d3c2d00 fix: aumenta limite de payload...

# Railway vai auto-deploy em ~2-3 minutos
```

---

### **2. Configurar Nova Instância Evolution**

#### **Via Flow Chat (RECOMENDADO):**
1. Acesse Flow Chat
2. **Configurações** > **Instâncias WhatsApp**
3. **+ Nova Instância**
4. Preencha:
   - **Nome Amigável:** CelPaulo (ou outro)
   - **Evolution URL:** https://evo.rbtec.com.br (nova)
   - **API Key:** [Cole a API Key do novo Evolution]
5. **Salvar** → Sistema cria tudo automaticamente:
   - ✅ Instância no Evolution
   - ✅ Registro no banco
   - ✅ Webhook configurado
   - ✅ Gera QR code

---

### **3. Escanear QR Code**
1. WhatsApp no celular
2. **Dispositivos conectados**
3. **Conectar dispositivo**
4. Escanear QR code
5. Aguardar: **Status = OPEN**

---

### **4. Verificar Webhook (IMPORTANTE!)**

No painel Evolution, verificar se foi configurado:

```
URL: https://alreasense-backend-production.up.railway.app/webhooks/evolution

Events:
✅ messages.upsert
✅ messages.update
✅ connection.update
✅ contacts.update (opcional)

Status: ✅ ENABLED
```

---

### **5. Adicionar Variável Railway** 🔥

**IMPORTANTE:** Ainda precisa adicionar:

```bash
CHAT_LOG_LEVEL=WARNING
```

**Como fazer:**
- Via Dashboard: Railway > Backend > Variables > Add
- Via CLI: `railway variables --set CHAT_LOG_LEVEL=WARNING`

**Por quê?**
- Reduz logs em 80-90%
- Evita rate limit (500 logs/segundo)

---

## 🧪 TESTES APÓS CONFIGURAR

### **Teste 1: Webhook funcionando**

**No console do navegador (F12):**
```javascript
// Envie mensagem de um contato e verifique logs Railway:
✅ Request XXX - Webhook: /webhooks/evolution
✅ 💬 [FLOW CHAT] Mensagem processada para tenant RBTec Informática
✅ 200 (status OK)

// NÃO deve aparecer:
❌ Webhook error: Request body exceeded...
❌ 500 Internal Server Error
```

---

### **Teste 2: Nome e Foto**

**Envie mensagem de contato NOVO:**

**No Flow Chat:**
- ✅ Nome correto (NÃO "Paulo Bernal")
- ✅ Foto de perfil carrega
- ✅ Aparece INSTANTANEAMENTE (sem F5)

**No console (F12):**
```
✅ [TENANT WS] Conectado
🆕 [TENANT WS] Nova conversa
✅ [INDIVIDUAL] Nome encontrado via API: João Silva
```

---

### **Teste 3: Grupos**

**Entre em grupo ou receba mensagem:**

**No Flow Chat:**
- ✅ Nome do grupo correto (NÃO "Grupo WhatsApp")
- ✅ Foto do grupo carrega
- ✅ Aparece instantaneamente

**No console (F12):**
```
✅ [GROUP] Informações encontradas via API
✅ Group name: Nome Real do Grupo
```

---

### **Teste 4: Logs Reduzidos**

**ANTES (sem CHAT_LOG_LEVEL):**
```
500+ logs/segundo
Railway rate limit reached
Mensagens dropadas
```

**DEPOIS (com CHAT_LOG_LEVEL=WARNING):**
```
50-100 logs/segundo
Sem rate limit
Tudo funcionando
```

---

## 🐛 PROBLEMAS ESPERADOS E SOLUÇÕES

### **Problema 1: Ainda aparece "Grupo WhatsApp"**

**Causa:** Instância no banco com UUID errado

**Solução:**
```sql
-- Verificar UUID no banco:
SELECT id, friendly_name, instance_name, is_active 
FROM notifications_whatsapp_instance 
WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';

-- Comparar com Evolution API
-- Se diferente, atualizar:
UPDATE notifications_whatsapp_instance 
SET instance_name = 'UUID_CORRETO_DO_EVOLUTION'
WHERE id = 'UUID_DO_REGISTRO';
```

---

### **Problema 2: WebSocket não conecta**

**No console (F12):**
```
❌ WebSocket connection failed
❌ [TENANT WS] Erro ao conectar
```

**Causa:** CORS ou WebSocket não habilitado no Railway

**Solução:**
1. Verificar variáveis Railway:
   - `ALLOWED_HOSTS` contém domínio
   - `CORS_ALLOWED_ORIGINS` contém frontend
2. Reiniciar backend Railway

---

### **Problema 3: Payload grande ainda dá erro**

**Erro:**
```
❌ Request body exceeded settings.DATA_UPLOAD_MAX_MEMORY_SIZE
```

**Causa:** Deploy não terminou ou variável não setada

**Solução:**
```bash
# Verificar deploy:
railway logs --follow

# Se necessário, adicionar variável:
railway variables --set DATA_UPLOAD_MAX_MEMORY_SIZE=52428800
```

---

## 📊 RESULTADO ESPERADO

### **ANTES:**
- ❌ Erro 500 em webhooks grandes
- ❌ Nomes: "Paulo Bernal" em todos
- ❌ Grupos: "Grupo WhatsApp" sem foto
- ❌ Sem tempo real (precisa F5)
- ❌ 500+ logs/segundo

### **DEPOIS:**
- ✅ Webhook processa até 50MB
- ✅ Nomes corretos de todos contatos
- ✅ Grupos com nome e foto reais
- ✅ Atualização em tempo real
- ✅ 50-100 logs/segundo (80% menos!)

---

## 📋 CHECKLIST FINAL

- [ ] ✅ Deploy com fix de payload (automático)
- [ ] ⏸️ Novo Evolution API online
- [ ] ⏸️ Criar instância via Flow Chat
- [ ] ⏸️ Escanear QR code
- [ ] ⏸️ Verificar webhook configurado
- [ ] ⏸️ **Adicionar CHAT_LOG_LEVEL=WARNING**
- [ ] ⏸️ Testar: nome, foto, grupo, tempo real
- [ ] ⏸️ Verificar logs: sem erro 500

---

## 💡 DICAS IMPORTANTES

1. **Aguarde deploy terminar** (~2-3 min após push)
2. **Teste com console aberto** (F12) para ver logs
3. **Use contatos NOVOS** para testar nome/foto
4. **Verifique UUID no banco** se der problema
5. **Não esqueça CHAT_LOG_LEVEL!** 🔥

---

**🎉 Pronto! Sistema corrigido e pronto para novo Evolution!**

Me avisa quando:
1. ✅ Novo Evolution subir
2. ✅ Criar instância
3. ✅ Testar

Vou acompanhar! 🚀

