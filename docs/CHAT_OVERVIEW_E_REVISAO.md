# Flow Chat – Overview e Revisão das Correções

## 1. Visão Geral da Arquitetura

### 1.1 Backend (Django)

**Models principais:**
- `Conversation` – tenant, department, contact_phone, status (pending/open/closed), instance_name
- `Message` – conversation, sender, content, direction (incoming/outgoing), status (sent/delivered/seen)
- `MessageAttachment` – message, file_url, media_hash, short_url, transcription
- `MessageReaction` – message, user/external_sender, emoji

**Fluxos principais:**

1. **Mensagens recebidas (Evolution → Webhook)**
   - `apps.connections.webhook_views` recebe `messages.upsert`
   - Chama `handle_message_upsert` em `apps.chat.webhooks`
   - Cria/atualiza `Conversation` e `Message`
   - Faz broadcast: `conversation_updated` (on_commit) + `message_received` (síncrono)
   - Mídia: enfileira `process_incoming_media` (RabbitMQ) → S3 + cache Redis

2. **Mensagens enviadas**
   - Via WebSocket: `handle_send_message` → cria Message → enfileira `send_message_to_evolution`
   - Via upload: `upload-presigned-url` → S3 → `confirm-upload` → Message + broadcast
   - Tasks: `tasks.send_message_to_evolution` envia para Evolution API e faz broadcast

3. **WebSocket (Django Channels)**
   - `ChatConsumerV2`: 1 conexão por usuário em `chat_tenant_{tenant_id}`
   - Subscribe/unsubscribe por conversa: `chat_tenant_{tenant_id}_conversation_{conv_id}`
   - Eventos: `message_received`, `conversation_updated`, `message_status_update`, `typing`, etc.

### 1.2 Frontend (React + Zustand)

**Store (`chatStore.ts`):**
- Estado normalizado: `messages.byId`, `messages.byConversationId`
- `addMessage` exige conversa existente no store (ou ativa)
- `upsertConversation` (conversationUpdater): merge com debounce 100ms

**Hooks:**
- `useTenantSocket` – conexão única ao WebSocket do tenant, trata eventos globais
- `useChatSocket` – subscribe na conversa ativa, envia mensagens
- `ChatWebSocketManager` – singleton do WebSocket

**Componentes principais:**
- `ConversationList` – lista com filtro por department (Inbox, Minhas Conversas, por departamento)
- `MessageList` – mensagens da conversa ativa, fetch paginado, merge com WebSocket
- `MessageInput` – texto, upload, respostas rápidas, menções

---

## 2. Correções Implementadas (Resumo)

| Correção | Arquivo | Descrição |
|----------|---------|-----------|
| **Imagem na 1ª vez** | `MessageInput.tsx` | Usa resposta do `confirm-upload` para `addMessage` imediato |
| **1ª msg individual** | `useTenantSocket.ts` | Se conversa não existe ao receber `message_received`, adiciona antes de `addMessage` |
| **Auto-abrir** | `useTenantSocket.ts` | Se em `/chat` sem conversa ativa, define a nova conversa como ativa |
| **IDs case-insensitive** | `useTenantSocket.ts` | `convIdNorm` para comparação consistente de UUIDs |
| **Status seen não reverter** | `webhooks.py` | Ignora `delivered`/`sent` para mensagens incoming já `seen` |
| **Individual → Inbox** | `webhooks.py` | Conversas individuais incoming vão para Inbox (department=null, pending) |
| **message_received com conversation** | `webhooks.py` | `broadcast_message_to_websocket` agora inclui conversation completa no tenant_group |
| **send_message multi-instância** | `tasks.py` | Prioriza `conversation.instance_name` antes de fallback para primeira instância |
| **/start multi-instância** | `views.py` | Aceita `instance_id`/`instance_name` na busca e criação; filtra por instância quando tenant tem 2+ |
| **Secretária typing** | `secretary_service.py` | `_send_typing_indicator` prioriza `conversation.instance_name` |
| **NewConversationModal** | `NewConversationModal.tsx` | Seletor de instância quando tenant tem 2+ (envia `instance_id` para /start) |

---

## 3. Revisão e Melhorias Sugeridas

### 3.1 Consistência: `addMessage` e `conversationExists`

**Problema potencial:** No `chatStore.addMessage`, a checagem `conversationExists` usa comparação estrita:

```typescript
const conversationExists = state.conversations.some(conv => 
  String(conv.id) === messageConversationId
);
```

O `useTenantSocket` usa `convIdNorm` (lowercase) para a mesma lógica. Se UUIDs vierem com casing diferente, pode haver inconsistência.

**Sugestão:** Usar `normalizeConversationKey` no `addMessage` para alinhar com o restante do store:

```typescript
const convKeyNorm = normalizeConversationKey(messageConversationId);
const conversationExists = state.conversations.some(conv => 
  normalizeConversationKey(conv.id) === convKeyNorm
);
```

### 3.2 Redução de logs em produção

Vários `console.log` em `useTenantSocket` e `chatStore` podem poluir o console em produção. Sugestão: condicionar a `import.meta.env.DEV` ou a uma flag de debug.

### 3.3 `broadcast_message_received` sem `conversation`

Em `utils/websocket.py`, `broadcast_message_received` envia apenas `message` e `conversation_id`. O webhook envia `conversation` completa via `channel_layer.group_send` direto. A função `broadcast_message_received` é usada em outros pontos – vale garantir que quem chama passe `conversation` quando disponível para manter o fluxo que depende de `data.conversation` no frontend.

### 3.4 Ordem de eventos no backend

`message_received` é enviado antes do commit (dentro da transação), enquanto `conversation_updated` é enviado em `transaction.on_commit`. Por isso o frontend recebe `message_received` primeiro e precisa adicionar a conversa quando ela ainda não existe. A solução atual cobre isso; uma alternativa seria mover `message_received` para `on_commit` para preservar a ordem lógica, mas isso exigiria refatoração maior.

### 3.5 Configuração: Inbox vs default_department para individual

A regra atual envia todas as conversas individuais incoming para o Inbox. Se um tenant quiser que conversas novas de um número específico (ex.: suporte) caiam direto em um departamento, seria necessário um mecanismo de configuração (ex.: routing por número ou tag). Por ora, o comportamento padrão (Inbox) é adequado para a maioria dos casos.

---

## 4. Fluxo Corrigido (Individual, 1ª Mensagem de Fora)

```
1. Evolution envia messages.upsert
2. connections webhook → handle_message_upsert (chat.webhooks)
3. use_inbox_for_new = True (individual + incoming)
   → defaults: department=null, status='pending'
4. get_or_create Conversation
5. Criar Message
6. channel_layer.group_send message_received (síncrono, antes do commit)
7. transaction.on_commit → broadcast_conversation_updated

--- Frontend ---
8. useTenantSocket recebe message_received
9. Conversa não está no store → addConversation(data.conversation)
10. Se em /chat e sem conversa ativa → setActiveConversation
11. addMessage(data.message)
12. updateConversation(data.conversation)
13. ConversationList filtra: Inbox = department=null E status=pending → passa
14. Conversa aparece no Inbox com badge
```

---

## 5. Conclusão

As correções cobrem:

- Exibição imediata de imagens enviadas
- Aparecimento da 1ª mensagem em conversas individuais
- Mantenção do status de leitura (seen) mesmo com eventos atrasados
- Roteamento de conversas individuais novas para o Inbox

A melhoria de consistência mais relevante sem quebrar o fluxo é usar `normalizeConversationKey` em `addMessage` para a checagem de `conversationExists`, garantindo robustez com variações de casing de UUIDs.
