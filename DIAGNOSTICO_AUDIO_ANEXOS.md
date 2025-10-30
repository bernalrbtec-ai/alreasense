# 🔍 DIAGNÓSTICO: ÁUDIO RECEBIDO NÃO TOCA

## ❌ PROBLEMA ATUAL:

Frontend mostra erro:
```javascript
NotSupportedError: The element has no supported sources.
```

## 📊 O QUE ESTÁ ACONTECENDO:

1. ✅ **Webhook recebe mensagem de áudio** do WhatsApp
2. ✅ **Cria MessageAttachment** no banco
3. ✅ **URL do WhatsApp é salva** em `attachment.file_url`
4. ❌ **Download NUNCA acontece!**
5. ❌ **Frontend recebe URL do WhatsApp** (não S3)
6. ❌ **Browser não consegue tocar** (CORS/criptografia)

---

## 🔍 LOGS QUE DEVERIAM APARECER (MAS NÃO APARECEM):

```log
📎 [WEBHOOK] Criado anexo ID=xxx, mime=audio/ogg, file=xxx.ogg
📎 [WEBHOOK] URL=https://mmg.whatsapp.net/...
🔄 [WEBHOOK] Enfileirando download do anexo xxx...
🚀 [RABBITMQ] Tentando enfileirar: chat_download_attachment
✅ [RABBITMQ] Mensagem publicada na fila 'chat_download_attachment'
✅ [RABBITMQ] Task enfileirada com sucesso: chat_download_attachment
📥 [DOWNLOAD] Iniciando download de anexo...
✅ [DOWNLOAD] Anexo baixado com sucesso!
📡 [STORAGE] Broadcast de anexo baixado enviado via WebSocket
```

---

## 🚀 DEPLOY COM LOGS DE DEBUG:

**Commit:** `eb7b9be` - Debug: Add detailed logs for attachment download queue

### O que foi adicionado:

1. **Logs no webhook** (`webhooks.py`):
   - Antes de criar anexo
   - Depois de criar anexo (com ID e URL)
   - Antes de enfileirar download
   - Depois de enfileirar (sucesso ou erro)

2. **Logs na função `delay()`** (`tasks.py`):
   - Antes de conectar ao RabbitMQ
   - Depois de conectar
   - Depois de declarar fila
   - Depois de publicar mensagem
   - **Re-raise exceptions** para ver erros

---

## 🧪 TESTE APÓS DEPLOY (2-3 min):

1. ✅ Aguardar deploy no Railway
2. 📱 Enviar áudio do WhatsApp
3. 👀 Observar logs do Railway
4. 📝 Procurar por:
   - `📎 [WEBHOOK] Criado anexo ID=...`
   - `🚀 [RABBITMQ] Tentando enfileirar...`
   - `❌ [RABBITMQ] ERRO...` (se houver)
   - `📥 [DOWNLOAD] Iniciando download...` (se chegar no consumer)

---

## 🎯 POSSÍVEIS CAUSAS:

### Hipótese 1: Worker não está rodando ❓
- Consumer que processa `chat_download_attachment` não está ativo
- **Como verificar:** Ver se há logs de `[CHAT CONSUMER] Consumers iniciados`

### Hipótese 2: Erro ao publicar na fila ❓
- `transaction.on_commit()` falhando silenciosamente
- RabbitMQ não acessível
- **Como verificar:** Novos logs vão mostrar

### Hipótese 3: Erro no consumer ❓
- Consumer recebe mensagem mas falha ao processar
- **Como verificar:** Ver logs de erro `[CHAT CONSUMER] Erro download_attachment`

---

## 📚 ARQUIVOS MODIFICADOS:

- `backend/apps/chat/webhooks.py` - Logs no enfileiramento
- `backend/apps/chat/tasks.py` - Logs na publicação RabbitMQ

---

## 🔄 PRÓXIMOS PASSOS:

1. ⏳ Aguardar deploy (2-3 min)
2. 📱 Testar envio de áudio do WhatsApp
3. 📊 Analisar logs detalhados
4. 🛠️ Corrigir problema identificado

---

**Status:** ⏳ Deploy em andamento...  
**Commit:** `eb7b9be`  
**Branch:** `main`



