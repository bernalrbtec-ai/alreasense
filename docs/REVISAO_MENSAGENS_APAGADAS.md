# Revisão: Mensagens Apagadas - Melhorias sem quebrar

> **Status:** Implementado em 10/02/2025

## Requisito do usuário
- **Mostrar** que a mensagem foi apagada: exibir "Mensagem apagada"
- **Não exibir** o conteúdo em: barra lateral, reply, forward

---

## Estado atual

### ✅ Já implementado
| Local | Comportamento |
|-------|---------------|
| **MessageList** (chat) | Mostra "Esta mensagem foi apagada" quando `is_deleted` (linha 958-964) |
| **ReplyPreview** (mensagem respondida no chat) | Mostra "Mensagem apagada" quando `repliedMessage.is_deleted` (linha 103-118) |
| **Webhook** | Processa `messages.delete`, marca `is_deleted=True`, faz broadcast |
| **Modelo** | Campos `is_deleted` e `deleted_at` existem |
| **Store** | `updateMessageDeleted` existe |

### ❌ Pendente / problema
| Local | Problema | Impacto |
|-------|----------|---------|
| **Barra lateral (ConversationList)** | Exibe `last_message.content` sem checar `is_deleted` (linha 519-525) | Mostra conteúdo da mensagem apagada |
| **MessageInput** (preview de reply) | Exibe `replyToMessage.content` sem checar `is_deleted` (linha 480-487) | Mostra conteúdo ao responder mensagem apagada |
| **ForwardMessageModal** | Não valida `is_deleted` ao abrir nem no preview (linha 238-240) | Permite abrir modal e vê conteúdo |
| **Backend last_message** | `last_message_queryset` e serializer não filtram `is_deleted` | Última mensagem pode ser apagada |
| **Backend unread_count** | Não filtra `is_deleted` | Mensagens apagadas contam como não lidas |
| **Backend MessageSerializer** | Retorna `content` mesmo quando `is_deleted=True` | Conteúdo vaza na API |
| **Backend websocket** | `broadcast_conversation_updated` não filtra `is_deleted` no fallback | Last message via WS pode ser apagada |

---

## Melhorias propostas (ordem de prioridade)

### 1. Backend - MessageSerializer: ocultar conteúdo quando apagada
**Arquivo:** `backend/apps/chat/api/serializers.py`  
**Risco:** Baixo  
**Onde:** No `to_representation` do MessageSerializer, após `data = super().to_representation(instance)`:

```python
# Se mensagem foi apagada, não expor conteúdo/attachments
if instance.is_deleted:
    data['content'] = ''
    data['attachments'] = []  # Ou manter array vazio
    # Manter is_deleted=True para frontend saber que exibir "Mensagem apagada"
```

**Efeito:** Em qualquer lugar que use a API, o conteúdo não será exposto. Frontend continua recebendo `is_deleted=True` e pode mostrar "Mensagem apagada".

---

### 2. Backend - last_message: ignorar mensagens apagadas
**Arquivo:** `backend/apps/chat/api/views.py` (linha ~333) e `utils/websocket.py` (linha ~81)  
**Risco:** Médio (última msg pode virar `None`)  

**views.py – `last_message_queryset`:**
```python
last_message_queryset = Message.objects.filter(
    is_deleted=False  # Excluir apagadas
).select_related('sender', 'conversation').prefetch_related('attachments').order_by('-created_at')[:1]
```

**serializers.py – `get_last_message`:**
- Se `last_message_list` existir e a primeira msg estiver `is_deleted`, buscar próxima não apagada.
- Fallback: `obj.messages.filter(is_deleted=False).order_by('-created_at').first()`.

**websocket.py – fallback:**
```python
last_msg = Message.objects.filter(
    conversation=conversation,
    is_deleted=False
).select_related(...).order_by('-created_at').first()
```

**Efeito:** Barra lateral mostra a última mensagem não apagada (ou "Nova conversa" se não houver).

**Observação:** O usuário quer ver "Mensagem apagada" na barra lateral. Há duas abordagens:
- **A)** Filtrar e mostrar a mensagem anterior não apagada.
- **B)** Manter last_message como a apagada, mas com conteúdo mascarado (via serializer), e no frontend mostrar "Mensagem apagada".

Recomendação: **A** (filtrar). Na barra lateral o preview passa a ser da última mensagem válida; na conversa, o usuário continua vendo "Esta mensagem foi apagada".

---

### 3. Backend - unread_count: ignorar mensagens apagadas
**Arquivos:** `views.py` (linha ~319) e `websocket.py` (linha ~110)  
**Risco:** Baixo  

**views.py:**
```python
filter=Q(
    messages__direction='incoming',
    messages__status__in=['sent', 'delivered'],
    messages__is_deleted=False  # Novo
),
```

**websocket.py:** Mesmo filtro em `unread_count_annotated`.

---

### 4. Frontend - ConversationList: fallback na barra lateral
**Arquivo:** `frontend/src/modules/chat/components/ConversationList.tsx` (linha 519-525)  
**Risco:** Baixo  

```tsx
{conversationItem.last_message ? (
  <p className="text-sm text-gray-600 dark:text-gray-400 truncate">
    {conversationItem.last_message?.is_deleted
      ? 'Mensagem apagada'
      : (conversationItem.conversation_type === 'group' && conversationItem.last_message?.sender_name
          ? `${conversationItem.last_message.sender_name}: ${conversationItem.last_message.content || ''}`
          : (conversationItem.last_message?.content || '📎 Anexo'))}
  </p>
) : (
  ...
)}
```

**Efeito:** Mesmo que o backend ainda envie last_message apagada, o frontend mostra "Mensagem apagada" em vez do conteúdo.

---

### 5. Frontend - MessageInput: preview de reply
**Arquivo:** `frontend/src/modules/chat/components/MessageInput.tsx` (linha 468-488)  
**Risco:** Baixo  

**Alteração 1 – preview:** Se `replyToMessage.is_deleted`, mostrar "Mensagem apagada" em vez de conteúdo.  
**Alteração 2 – envio:** Se `replyToMessage?.is_deleted`, fazer `clearReply()`, mostrar toast e não enviar.

---

### 6. Frontend - ForwardMessageModal: bloquear mensagens apagadas
**Arquivo:** `frontend/src/modules/chat/components/ForwardMessageModal.tsx`  
**Risco:** Baixo  

**Alteração 1:** No início do componente, se `message.is_deleted`:
- Mostrar toast de erro.
- Chamar `onClose()`.
- Retornar `null` (não abrir o modal).

**Alteração 2:** No preview (linha 238-240): se `message.is_deleted`, mostrar "Mensagem apagada" em vez de conteúdo.

---

### 7. Backend - forward_message e reply: validação
**Arquivo:** `views.py` – action `forward_message`  
**Risco:** Baixo  

Antes de encaminhar:
```python
if message.is_deleted:
    return Response({'error': 'Não é possível encaminhar uma mensagem que foi apagada'}, status=400)
```

**Arquivo:** `tasks.py` / `consumers_v2.py` – envio com reply  
**Risco:** Baixo  

Incluir `is_deleted=False` no filtro da mensagem original e, se não existir, seguir envio sem reply.

---

## Ordem de implementação sugerida

1. **MessageSerializer** – mascarar conteúdo quando `is_deleted` (segurança em toda a API).
2. **ConversationList** – fallback "Mensagem apagada" na barra lateral.
3. **MessageInput** – checar `is_deleted` no preview e no envio.
4. **ForwardMessageModal** – bloquear abertura e ajustar preview.
5. **Backend** – filtros em `last_message`, `unread_count` e websocket.
6. **Backend** – validações em `forward_message` e reply.

---

## Garantias para não quebrar

- Manter `is_deleted` na API para o frontend decidir o que exibir.
- Frontend com fallbacks antes de mudar o backend (ex.: ConversationList).
- Backend com validações explícitas (forward, reply).
- Índice em `is_deleted` já existe no modelo.

---

## Resumo (implementado)

| Item | Tipo | Status |
|------|------|--------|
| MessageSerializer mascarar conteúdo | Backend | ✅ |
| ConversationList fallback | Frontend | ✅ |
| MessageInput reply (preview + bloqueio) | Frontend | ✅ |
| ForwardMessageModal (bloqueio) | Frontend | ✅ |
| Filtros last_message | Backend | ✅ |
| Filtro unread_count | Backend | ✅ |
| Validação forward (API) | Backend | ✅ |
| MessageContextMenu: ocultar Responder/Encaminhar/Apagar | Frontend | ✅ |
