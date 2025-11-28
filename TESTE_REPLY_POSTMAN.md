# 🧪 Teste de Reply via Postman

## 📋 Formato do Payload

### 1️⃣ **Via WebSocket (Formato Real)**

O sistema usa WebSocket, então o Postman precisa suportar WebSocket. O payload é enviado como mensagem JSON via WebSocket.

**URL WebSocket:**
```
wss://alreasense-backend-production.up.railway.app/ws/chat/tenant/{tenant_id}/?token={JWT_TOKEN}
```

**Mensagem JSON a enviar:**
```json
{
  "type": "send_message",
  "conversation_id": "16dc0740-fb38-433b-914a-cdf3a94606c5",
  "content": "Esta é uma mensagem de teste com reply",
  "include_signature": true,
  "is_internal": false,
  "reply_to": "8531f51f-e330-4751-abcc-1f182869d1dc",
  "mentions": []
}
```

**Campos:**
- `type`: **Obrigatório** - Sempre `"send_message"`
- `conversation_id`: **Obrigatório** - UUID da conversa (string)
- `content`: **Obrigatório** - Texto da mensagem (string)
- `include_signature`: **Opcional** - Se inclui assinatura (boolean, default: `true`)
- `is_internal`: **Opcional** - Se é nota interna (boolean, default: `false`)
- `reply_to`: **Opcional** - UUID da mensagem sendo respondida (string)
- `mentions`: **Opcional** - Array de números mencionados (array de strings, apenas para grupos)
- `attachment_urls`: **Opcional** - Array de URLs de anexos (array de strings)

### 2️⃣ **Exemplo Completo - Mensagem Normal (sem reply)**

```json
{
  "type": "send_message",
  "conversation_id": "16dc0740-fb38-433b-914a-cdf3a94606c5",
  "content": "Olá, como posso ajudar?",
  "include_signature": true,
  "is_internal": false
}
```

### 3️⃣ **Exemplo Completo - Mensagem com Reply**

```json
{
  "type": "send_message",
  "conversation_id": "16dc0740-fb38-433b-914a-cdf3a94606c5",
  "content": "Esta é minha resposta",
  "include_signature": true,
  "is_internal": false,
  "reply_to": "8531f51f-e330-4751-abcc-1f182869d1dc"
}
```

**Onde obter o `reply_to`:**
- É o `id` (UUID) da mensagem original que você quer responder
- Você pode obter listando as mensagens da conversa: `GET /api/chat/conversations/{conversation_id}/messages/`
- O `id` da mensagem que você quer responder é o `reply_to`

### 4️⃣ **Exemplo Completo - Mensagem com Reply e Menções (Grupo)**

```json
{
  "type": "send_message",
  "conversation_id": "16dc0740-fb38-433b-914a-cdf3a94606c5",
  "content": "@5511999999999 @5511888888888 Olá pessoal!",
  "include_signature": true,
  "is_internal": false,
  "reply_to": "8531f51f-e330-4751-abcc-1f182869d1dc",
  "mentions": ["5511999999999", "5511888888888"]
}
```

## 🔌 Como Testar no Postman

### Opção 1: WebSocket (Recomendado)

1. **Criar nova requisição WebSocket:**
   - New → WebSocket Request
   - URL: `wss://alreasense-backend-production.up.railway.app/ws/chat/tenant/{tenant_id}/?token={JWT_TOKEN}`
   - Substituir `{tenant_id}` pelo UUID do seu tenant
   - Substituir `{JWT_TOKEN}` pelo token JWT válido

2. **Conectar:**
   - Clicar em "Connect"
   - Deve aparecer "Connected"

3. **Subscribe na conversa (obrigatório antes de enviar):**
   ```json
   {
     "type": "subscribe",
     "conversation_id": "16dc0740-fb38-433b-914a-cdf3a94606c5"
   }
   ```

4. **Enviar mensagem com reply:**
   ```json
   {
     "type": "send_message",
     "conversation_id": "16dc0740-fb38-433b-914a-cdf3a94606c5",
     "content": "Teste de reply",
     "reply_to": "8531f51f-e330-4751-abcc-1f182869d1dc"
   }
   ```

### Opção 2: API REST (Alternativa)

Se não conseguir via WebSocket, você pode criar uma mensagem diretamente via API REST:

**Endpoint:**
```
POST /api/chat/messages/
```

**Headers:**
```
Authorization: Bearer {JWT_TOKEN}
Content-Type: application/json
```

**Body:**
```json
{
  "conversation": "16dc0740-fb38-433b-914a-cdf3a94606c5",
  "content": "Teste de reply via API",
  "metadata": {
    "reply_to": "8531f51f-e330-4751-abcc-1f182869d1dc",
    "include_signature": true
  }
}
```

**⚠️ IMPORTANTE:** Esta rota pode não existir ou pode ter validações diferentes. O método recomendado é via WebSocket.

## 📝 Como Obter os IDs Necessários

### 1. **Obter Tenant ID:**
```bash
GET /api/auth/user/
Authorization: Bearer {JWT_TOKEN}
```
Resposta contém `tenant_id`

### 2. **Obter JWT Token:**
```bash
POST /api/auth/login/
Content-Type: application/json

{
  "email": "seu@email.com",
  "password": "sua_senha"
}
```
Resposta contém `access` (token JWT)

### 3. **Listar Conversas:**
```bash
GET /api/chat/conversations/
Authorization: Bearer {JWT_TOKEN}
```
Resposta contém array de conversas com `id`

### 4. **Listar Mensagens de uma Conversa:**
```bash
GET /api/chat/conversations/{conversation_id}/messages/
Authorization: Bearer {JWT_TOKEN}
```
Resposta contém array de mensagens com `id` (este é o `reply_to`)

## 🔍 Verificar se Funcionou

### 1. **Verificar no Banco (via API):**
```bash
GET /api/chat/messages/{message_id}/
Authorization: Bearer {JWT_TOKEN}
```

Verificar se `metadata.reply_to` está presente:
```json
{
  "id": "...",
  "content": "Teste de reply",
  "metadata": {
    "reply_to": "8531f51f-e330-4751-abcc-1f182869d1dc",
    "include_signature": true
  }
}
```

### 2. **Verificar Logs do Backend:**
Procurar por:
- `📥 [CHAT WS V2] Recebido send_message:` (deve mostrar `reply_to`)
- `💬 [CHAT WS V2] Reply_to adicionado ao metadata: ...`
- `💬 [CHAT ENVIO] Mensagem é resposta de: ...`
- `💬 [CHAT ENVIO] Adicionando options.quoted ao texto`

### 3. **Verificar no Frontend:**
- Abrir console do navegador
- Procurar por:
  - `📤 [HOOK] Enviando mensagem com reply: ...`
  - `💬 [HOOK] ✅ Mensagem tem reply_to: ...`
  - Preview da mensagem original deve aparecer na mensagem enviada

## 🐛 Troubleshooting

### Problema: "Nenhuma conversa ativa"
**Solução:** Enviar `subscribe` antes de `send_message`:
```json
{
  "type": "subscribe",
  "conversation_id": "16dc0740-fb38-433b-914a-cdf3a94606c5"
}
```

### Problema: "Token JWT inválido"
**Solução:** 
- Verificar se token não expirou
- Obter novo token via `/api/auth/login/`
- Token deve estar na query string: `?token={JWT_TOKEN}`

### Problema: "reply_to não encontrado"
**Solução:**
- Verificar se o UUID da mensagem original está correto
- Verificar se a mensagem original pertence à mesma conversa
- Verificar se a mensagem original tem `message_id` (Evolution ID) preenchido

### Problema: "Mensagem não aparece com preview"
**Solução:**
- Verificar se `metadata.reply_to` está presente na resposta da API
- Verificar se a mensagem original está na lista de mensagens carregadas
- Verificar logs do frontend para ver se `reply_to` está sendo recebido

## 📊 Exemplo Completo de Fluxo

### 1. Conectar WebSocket:
```
wss://alreasense-backend-production.up.railway.app/ws/chat/tenant/a72fbca7-92cd-4aa0-80cb-1c0a02761218/?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 2. Subscribe na conversa:
```json
{
  "type": "subscribe",
  "conversation_id": "16dc0740-fb38-433b-914a-cdf3a94606c5"
}
```

### 3. Enviar mensagem com reply:
```json
{
  "type": "send_message",
  "conversation_id": "16dc0740-fb38-433b-914a-cdf3a94606c5",
  "content": "Esta é minha resposta à mensagem anterior",
  "include_signature": true,
  "is_internal": false,
  "reply_to": "8531f51f-e330-4751-abcc-1f182869d1dc"
}
```

### 4. Resposta Esperada:
```json
{
  "type": "message_received",
  "message": {
    "id": "nova-mensagem-uuid",
    "conversation": "16dc0740-fb38-433b-914a-cdf3a94606c5",
    "content": "*Paulo Bernal:*\n\nEsta é minha resposta à mensagem anterior",
    "direction": "outgoing",
    "status": "pending",
    "metadata": {
      "reply_to": "8531f51f-e330-4751-abcc-1f182869d1dc",
      "include_signature": true
    },
    "created_at": "2025-11-28T11:30:00Z"
  }
}
```

## ✅ Checklist de Teste

- [ ] WebSocket conectado com sucesso
- [ ] Subscribe na conversa funcionou
- [ ] Mensagem enviada com `reply_to` no payload
- [ ] Backend recebeu `reply_to` (verificar logs)
- [ ] `metadata.reply_to` foi salvo no banco
- [ ] Mensagem foi enviada para Evolution API com `options.quoted`
- [ ] Mensagem recebida de volta tem `metadata.reply_to`
- [ ] Frontend exibe preview da mensagem original

