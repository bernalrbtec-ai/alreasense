# 🔍 Debug do Fluxo de Reply

## ✅ Logs Adicionados

### Frontend

1. **useChatSocket.ts** (linha ~247):
   - Log quando `replyToMessageId` é fornecido
   - Log do payload completo antes de enviar
   - Log do resultado do `sendMessage`

2. **ChatWebSocketManager.ts** (linha ~253):
   - Log detalhado do payload sendo enviado via WebSocket
   - Inclui: `type`, `conversation_id`, `content`, `reply_to`, `include_signature`, `is_internal`, `mentions`

### Backend

1. **consumers_v2.py** (linha ~220):
   - Log quando recebe `send_message` com todos os dados
   - Log específico do `reply_to` recebido

2. **consumers_v2.py** (linha ~438):
   - Log quando `reply_to` é adicionado ao metadata
   - Log quando não há `reply_to`

3. **tasks.py** (linha ~652):
   - Log quando busca mensagem original para reply
   - Log do Evolution ID e RemoteJid encontrados
   - Log de erro se mensagem original não for encontrada

## 🧪 Como Testar

1. **Abrir console do navegador** (F12 → Console)

2. **Selecionar uma mensagem para responder**:
   - Clicar com botão direito na mensagem
   - Clicar em "Responder"
   - Verificar se aparece preview da mensagem no input

3. **Enviar a mensagem com reply**:
   - Digitar mensagem
   - Clicar em enviar
   - **Verificar logs no console:**
     - `📤 [HOOK] Enviando mensagem com reply: ...`
     - `📤 [HOOK] Payload completo: ...`
     - `📤 [MANAGER] Enviando send_message: ...`
     - `✅ [MANAGER] Mensagem enviada com sucesso: send_message`

4. **Verificar logs do backend** (Railway ou local):
   - `📥 [CHAT WS V2] Recebido send_message:`
   - `💬 [CHAT WS V2] Reply_to adicionado ao metadata: ...`
   - `💬 [CHAT ENVIO] Mensagem é resposta de: ...`

## 🔍 Pontos de Verificação

### Se `reply_to` não aparece no console do navegador:
- Verificar se `replyToMessage?.id` existe no `MessageInput.tsx` (linha 171)
- Verificar se `setReplyToMessage` foi chamado corretamente no `MessageContextMenu.tsx` (linha 191)

### Se `reply_to` não chega no backend:
- Verificar se WebSocket está conectado (`isConnected === true`)
- Verificar se `conversation_id` está correto no payload
- Verificar formato do JSON sendo enviado

### Se `reply_to` não é salvo no metadata:
- Verificar se `reply_to` não é `null` ou `undefined` no backend
- Verificar se `metadata` está sendo criado corretamente

### Se mensagem original não é encontrada:
- Verificar se `message_id` (Evolution ID) existe na mensagem original
- Verificar se `conversation` da mensagem original está correto
- Verificar se `contact_phone` da conversa está no formato correto

## 📋 Checklist de Debug

- [ ] Preview da mensagem aparece no input quando seleciona "Responder"?
- [ ] Log `📤 [HOOK] Enviando mensagem com reply` aparece no console?
- [ ] Log `📤 [MANAGER] Enviando send_message` mostra `reply_to`?
- [ ] Log `📥 [CHAT WS V2] Recebido send_message` mostra `reply_to`?
- [ ] Log `💬 [CHAT WS V2] Reply_to adicionado ao metadata` aparece?
- [ ] Log `💬 [CHAT ENVIO] Mensagem é resposta de` aparece?
- [ ] Mensagem é enviada com `options.quoted` para Evolution API?
- [ ] Quando recebe resposta do WhatsApp, `metadata.reply_to` está presente?
- [ ] Preview da mensagem original aparece na resposta recebida?

## 🐛 Problemas Comuns

### 1. `reply_to` é `undefined` no frontend
**Causa**: `replyToMessage` não está sendo setado corretamente
**Solução**: Verificar se `setReplyToMessage(message)` é chamado no `MessageContextMenu`

### 2. `reply_to` não chega no backend
**Causa**: WebSocket não está conectado ou payload está incorreto
**Solução**: Verificar logs do `ChatWebSocketManager` e conexão WebSocket

### 3. Mensagem original não encontrada
**Causa**: `message_id` (Evolution ID) não existe na mensagem original
**Solução**: Verificar se mensagem original foi enviada com sucesso e tem `message_id`

### 4. `quoted_remote_jid` incorreto
**Causa**: `contact_phone` da conversa está em formato incorreto
**Solução**: Verificar formato do telefone (deve ser `5517999999999@s.whatsapp.net` para individual)

## 📝 Próximos Passos

Após testar, compartilhar:
1. Logs do console do navegador
2. Logs do backend (se possível)
3. Screenshot do preview da mensagem (se aparecer)
4. Descrição do comportamento observado

