# 🔧 CORREÇÕES APLICADAS - INSTÂNCIAS WHATSAPP

## 🚨 PROBLEMA IDENTIFICADO

**Erro nos logs:**
```
⚠️ [REFRESH] Nenhuma instância ativa para tenant RBTec Informática
⚠️ [READ RECEIPT] Nenhuma instância ativa para tenant RBTec Informática
⚠️ [DELIVERY ACK] Nenhuma instância ativa para tenant RBTec Informática
```

**Causa Raiz:**
O código estava buscando `EvolutionConnection` (configuração do servidor Evolution) ao invés de `WhatsAppInstance` (instância específica do WhatsApp com UUID).

**Resultado:**
- ❌ Instância não encontrada
- ❌ Grupos sem nome/foto
- ❌ Contatos sem foto
- ❌ Confirmações de leitura não enviadas
- ❌ ACK de entrega não enviados

---

## ✅ CORREÇÕES APLICADAS

### **1. Payload muito grande (já corrigido antes)**
```python
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
```

### **2. Busca de instância corrigida**

**ANTES (ERRADO):**
```python
instance = EvolutionConnection.objects.filter(
    tenant=request.user.tenant,
    is_active=True
).first()
```

**DEPOIS (CORRETO):**
```python
# Buscar instância WhatsApp (tem o UUID)
wa_instance = WhatsAppInstance.objects.filter(
    tenant=request.user.tenant,
    is_active=True,
    status='active'
).first()

# Buscar servidor Evolution (config global)
evolution_server = EvolutionConnection.objects.filter(is_active=True).first()

# Usar dados combinados
base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
api_key = wa_instance.api_key or evolution_server.api_key
instance_name = wa_instance.instance_name  # ← UUID correto!
```

### **3. Arquivos corrigidos**

✅ `backend/apps/chat/api/views.py`:
- `refresh_info()` - Atualizar nome/foto de conversas
- `debug_list_groups()` - Debug de grupos

✅ `backend/apps/chat/webhooks.py`:
- `send_delivery_receipt()` - ACK de entrega (✓✓ cinza)
- `send_read_receipt()` - Confirmação de leitura (✓✓ azul)
- Busca de foto/nome ao criar conversa (linha ~218)
- Busca de info de grupo existente (linha ~386)

---

## 📊 RESULTADO ESPERADO

### **ANTES:**
- ❌ "Nenhuma instância ativa para tenant"
- ❌ Grupos: "Grupo WhatsApp" sem foto
- ❌ Contatos: sem foto
- ❌ Confirmações não enviadas
- ❌ Erro 500 em webhooks grandes

### **DEPOIS:**
- ✅ Instância encontrada corretamente
- ✅ Grupos com nome e foto reais
- ✅ Contatos com foto de perfil
- ✅ Confirmações de leitura funcionando (✓✓ azul)
- ✅ ACK de entrega funcionando (✓✓ cinza)
- ✅ Webhooks até 50MB processados

---

## 🎯 PRÓXIMOS PASSOS (VOCÊ FAZ)

### **1. Aguardar Deploy Railway** (⏳ ~2-3 minutos)
```bash
# Verificar:
git log --oneline -1
# Deve mostrar: fec4676 fix: corrige busca de instância WhatsApp
```

### **2. Criar Instância via Flow Chat**
1. Acesse Flow Chat
2. **Configurações** > **Instâncias WhatsApp**
3. **+ Nova Instância**
4. Preencha:
   - Nome: CelPaulo
   - Evolution URL: https://evo.rbtec.com.br
   - API Key: [do Evolution]
5. **Salvar**
6. **Escanear QR code**

### **3. Adicionar Variável Railway** 🔥

**IMPORTANTE:** Reduzir logs!

```bash
CHAT_LOG_LEVEL=WARNING
```

**Como:**
- Railway Dashboard > Backend > Variables > Add
- OU: `railway variables --set CHAT_LOG_LEVEL=WARNING`

### **4. Testar!** 🧪

**A. Console aberto (F12):**
```javascript
// Deve aparecer:
✅ [TENANT WS] Conectado
🆕 [TENANT WS] Nova conversa
✅ [INDIVIDUAL] Nome encontrado via API: João Silva
```

**B. Funcionalidades:**
- ✅ Nome correto (não "Paulo Bernal")
- ✅ Foto de perfil aparece
- ✅ Grupos com nome/foto reais
- ✅ Atualiza instantaneamente (sem F5)
- ✅ Confirmação de leitura (✓✓ azul)

**C. Logs Railway (verificar):**
- ✅ NÃO aparece mais "Nenhuma instância ativa"
- ✅ NÃO aparece erro 500
- ✅ Logs reduzidos (80-90% menos)

---

## 🐛 SE AINDA DER PROBLEMA

### **Problema: Ainda "Nenhuma instância ativa"**

**Verificar no banco:**
```sql
SELECT 
    id, 
    friendly_name, 
    instance_name,  -- ← Este é o UUID que precisa estar correto
    is_active, 
    status,
    tenant_id
FROM notifications_whatsapp_instance 
WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';
```

**O que checar:**
1. ✅ `is_active = TRUE`
2. ✅ `status = 'active'`
3. ✅ `instance_name` = UUID do Evolution (ex: `a396cd48-8114-4803-bad5-4a3e0191beaa`)
4. ✅ `tenant_id` correto

**Se UUID estiver errado:**
```sql
UPDATE notifications_whatsapp_instance 
SET instance_name = 'UUID_CORRETO_DO_EVOLUTION'
WHERE id = 'ID_DO_REGISTRO';
```

### **Problema: Grupos ainda sem nome/foto**

**Causa:** Instância criada mas não conectada no Evolution

**Solução:**
1. Verificar Evolution: Status = `OPEN`
2. Testar webhook: `POST /webhooks/evolution`
3. Abrir grupo no Flow Chat (dispara refresh automático)

### **Problema: Confirmações não funcionam**

**Verificar:**
1. Instância conectada (QR code escaneado)
2. Webhook configurado corretamente no Evolution
3. Logs Railway: procurar por "[DELIVERY ACK]" ou "[READ RECEIPT]"

---

## 📋 CHECKLIST FINAL

- [x] ✅ Fix payload 50MB (commit d3c2d00)
- [x] ✅ Fix busca instância (commit fec4676)  
- [x] ✅ Push para Railway
- [ ] ⏸️ **Deploy Railway terminar**
- [ ] ⏸️ **Criar instância via Flow Chat**
- [ ] ⏸️ **Adicionar CHAT_LOG_LEVEL=WARNING** 🔥
- [ ] ⏸️ **Escanear QR code**
- [ ] ⏸️ **Testar tudo funcionando**

---

## 💡 COMMITS APLICADOS

```bash
d3c2d00 - fix: aumenta limite de payload para webhooks Evolution (50MB)
fec4676 - fix: corrige busca de instância WhatsApp (usar WhatsAppInstance ao invés de EvolutionConnection)
```

---

**🎉 Sistema corrigido! Agora é só:**
1. ⏳ Aguardar deploy
2. 🔧 Criar instância
3. ✅ Adicionar variável CHAT_LOG_LEVEL
4. 🧪 Testar

**Me avisa quando tudo estiver pronto para testar!** 🚀

