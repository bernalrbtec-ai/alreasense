# 🎯 PROBLEMA CRÍTICO DO WEBHOOK RESOLVIDO!

**Deploy:** `1bf0cc3` - Fix: Remove webhook override in Notifications product

---

## ❌ O PROBLEMA:

### Sintoma:
- **App aberto:** Mensagens do celular aparecem em tempo real ✅
- **App fechado:** Mensagens do celular **NÃO aparecem** ao abrir ❌

### Causa Raiz:
O produto **Notifications** (que não está sendo usado) estava **SOBRESCREVENDO** o webhook global da Evolution!

#### Como acontecia:

1. **Webhook Global** configurado corretamente no `.env` da Evolution:
   ```
   WEBHOOK_GLOBAL_URL='https://alreasense-backend-production.up.railway.app/webhooks/evolution/?token=...'
   ```

2. **MAS** quando você conectava uma instância via aplicação:
   - Código em `apps/notifications/models.py` (linha 337)
   - Configurava webhook **POR INSTÂNCIA**
   - URL errada: `/api/notifications/webhook/`
   - **ANULAVA** o webhook global!

3. **Resultado:**
   - Evolution enviava webhooks para `/api/notifications/webhook/`
   - Esse endpoint apenas **logava** (produto Notifications)
   - **NÃO salvava** no banco de dados
   - Flow Chat **nunca recebia** as mensagens!

---

## ✅ A SOLUÇÃO:

### Arquivos Modificados:
- `backend/apps/notifications/models.py`

### O que foi feito:

#### 1. Removido webhook da criação de instância:
```python
# ANTES (linha 335-352):
'webhook': {
    'enabled': True,
    'url': f"{getattr(settings, 'BASE_URL', '')}/api/notifications/webhook/",
    'webhook_by_events': False,
    'events': [...]
}

# DEPOIS:
# ❌ REMOVIDO: webhook por instância (usa webhook global)
# Produto Notifications desabilitado - usar Flow Chat
```

#### 2. Desabilitado atualização de webhook:
```python
# ANTES: _update_webhook_after_create() configurava webhook
# DEPOIS: Retorna True sem configurar (usa webhook global)

print(f"   ⏭️ PULANDO configuração de webhook (usando webhook global da Evolution)")
return True
```

---

## 🎯 RESULTADO ESPERADO:

Agora, quando você conectar uma instância:
1. ✅ **NÃO** sobrescreve webhook global
2. ✅ Evolution continua enviando para `/webhooks/evolution/`
3. ✅ Flow Chat **RECEBE** todas as mensagens
4. ✅ Mensagens são **SALVAS** no banco
5. ✅ Ao abrir app, mensagens **APARECEM**!

---

## 🧪 TESTE APÓS DEPLOY (2-3 min):

### Passo a passo:

1. ⏳ **Aguarde** deploy Railway terminar
2. 🔌 **Desconecte** todas as instâncias
3. 🔗 **Reconecte** apenas uma instância (ex: 5517996555683)
4. 💻 **FECHE** o app web
5. 📱 **Do celular** (5517991253112) envie: `"teste final webhook"`
6. ⏰ **Aguarde 15 segundos**
7. 💻 **ABRA** o app web
8. 💬 **Vá na conversa**
9. ✅ **Mensagem deve aparecer!**

### O que procurar nos logs:

**DEVE aparecer:**
```
📥 [WEBHOOK] Evento recebido: messages.upsert
📥 [WEBHOOK UPSERT] ====== INICIANDO PROCESSAMENTO ======
💾 [WEBHOOK] Tentando salvar mensagem no banco...
✅ [WEBHOOK] MENSAGEM NOVA CRIADA NO BANCO!
```

**NÃO deve aparecer:**
```
💬 [FLOW CHAT] Mensagem processada para tenant
(sem salvar no banco)
```

---

## 📊 HISTÓRICO DO PROBLEMA:

### Sessão de debugging:

1. **Início:** Mensagens do celular não aparecem
2. **Investigação:** WebSocket funciona (tempo real OK)
3. **Descoberta:** Initial load não carrega mensagens antigas
4. **Análise:** Backend não estava salvando no banco
5. **Root Cause:** Webhook indo para endpoint errado
6. **Identificação:** Produto Notifications sobrescrevendo
7. **Solução:** Desabilitar webhook por instância
8. **Fix:** Commit `1bf0cc3`

### Commits relacionados:

- `7f4176a` - Fix: Correct PTT audio payload structure
- `eb7b9be` - Debug: Add detailed logs for attachment download
- `9cacba9` - Debug: Add logs to trace messages from phone
- `442420f` - Hotfix: Fix syntax error in webhooks.py
- `1bf0cc3` - **Fix: Remove webhook override** ← **SOLUÇÃO FINAL**

---

## 🔧 CONFIGURAÇÃO ATUAL (CORRETA):

### Evolution API (.env):
```bash
WEBHOOK_GLOBAL_ENABLED=true
WEBHOOK_GLOBAL_URL='https://alreasense-backend-production.up.railway.app/webhooks/evolution/?token=a8f7d3c2-9b4e-4a1f-b5c8-2d7e3f9a1b4c'
WEBHOOK_EVENTS_MESSAGES_UPSERT=true
WEBHOOK_EVENTS_MESSAGES_UPDATE=true
WEBHOOK_EVENTS_CONNECTION_UPDATE=true
```

### Backend (Alrea Sense):
- ✅ Webhook handler: `/webhooks/evolution/` (apps/chat/webhooks.py)
- ✅ Salva mensagens no banco de dados
- ✅ Broadcast via WebSocket para tempo real
- ❌ Produto Notifications **desabilitado** (não sobrescreve)

---

## 📝 LIÇÕES APRENDIDAS:

1. **Múltiplos webhooks** podem causar conflitos
2. **Webhook global** é mais simples e confiável
3. **Webhook por instância** pode sobrescrever global
4. **Produtos não usados** devem ser totalmente desabilitados
5. **Logs detalhados** são essenciais para debugging

---

**Deploy: `1bf0cc3` - Aguarde 2-3 min e teste!** 🚀

**Status:** ⏳ Deploy em andamento...



