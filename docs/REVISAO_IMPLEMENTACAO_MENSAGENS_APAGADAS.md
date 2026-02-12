# Revisão da Implementação: Mensagens Apagadas

## Visão geral

A implementação cobre os requisitos:
- **Mostrar** que a mensagem foi apagada: "Mensagem apagada" / "Esta mensagem foi apagada"
- **Não exibir** o conteúdo em: barra lateral, reply, forward

---

## ✅ Backend – O que está correto

### 1. MessageSerializer (`serializers.py`)
- Máscara `content` e `attachments` quando `is_deleted=True`
- Mantém `is_deleted=True` para o frontend exibir o indicador
- **Status:** OK

### 2. last_message – filtros
- **views.py** – Prefetch: `Message.objects.filter(is_deleted=False)...`
- **websocket.py** – `last_message_queryset` e fallback filtram `is_deleted=False`
- **serializers.py** – `get_last_message` (fallback) filtra `is_deleted=False`
- **Status:** OK

### 3. unread_count
- **views.py** e **websocket.py** – `Count(..., filter=Q(..., messages__is_deleted=False))`
- **Status:** OK

### 4. forward_message (API)
- Bloqueia encaminhamento com 400 se `message.is_deleted`
- **Status:** OK

### 5. Webhook `messages.delete`
- Marca `is_deleted=True`, chama `broadcast_message_deleted`
- Já considerava `is_deleted=False` na busca de mensagens
- **Status:** OK

---

## ✅ Frontend – O que está correto

### 1. MessageList
- Mostra "Esta mensagem foi apagada" para mensagens com `is_deleted`
- Esconde conteúdo e anexos quando `is_deleted`
- `ReplyPreview` mostra "Mensagem apagada" para mensagens respondidas apagadas
- **Status:** OK

### 2. ConversationList (barra lateral)
- Mostra "Mensagem apagada" quando `last_message?.is_deleted`
- Fallback defensivo caso o backend ainda envie mensagem apagada
- **Status:** OK

### 3. MessageInput (reply)
- Preview exibe "Mensagem apagada" quando `replyToMessage.is_deleted`
- Bloqueia envio e exibe toast se reply for de mensagem apagada
- **Status:** OK

### 4. MessageContextMenu
- Oculta Responder, Encaminhar e Apagar em mensagens apagadas
- **Status:** OK

---

## ✅ ForwardMessageModal – Corrigido (regras de Hooks)

**Problema original:** O early return estava antes de vários `useState`, violando as regras de Hooks do React.

**Correção aplicada:** Todos os hooks foram movidos para o topo do componente; o `return null` agora vem após todas as declarações de hooks.

---

## 🔍 Pontos para considerar (não obrigatórios)

### 1. Reply via API/WebSocket (tasks.py, consumers_v2.py)
- O backend aceita `reply_to` sem verificar se a mensagem está apagada.
- O frontend bloqueia isso; um cliente malicioso poderia enviar `reply_to` para mensagem apagada.
- **Risco:** baixo; comportamento estranho, mas sem impacto grave.
- **Sugestão:** adicionar validação opcional: se `reply_to` apontar para mensagem com `is_deleted=True`, ignorar ou retornar erro.

### 2. Preview no ForwardMessageModal
- O preview do modal usa `message.content`; com mensagem apagada o modal é fechado imediatamente, então o preview não chega a ser exibido.
- Se o bug de Hooks for corrigido, o fluxo continua correto: o early return evita mostrar o preview.

### 3. Ordenação da lista de conversas
- A ordenação usa `last_message_at` da conversa, não da última mensagem não apagada.
- Se a última mensagem for apagada, a conversa continua na mesma posição, o que costuma ser o esperado.
- **Status:** OK.

---

## Resumo

| Área           | Status   | Observação                                  |
|----------------|----------|---------------------------------------------|
| Backend        | ✅ OK    | Serializer, filtros e validações corretos   |
| MessageList    | ✅ OK    | Tratamento e exibição consistentes          |
| ConversationList | ✅ OK  | Fallback para "Mensagem apagada"            |
| MessageInput   | ✅ OK    | Preview e bloqueio de reply                 |
| MessageContextMenu | ✅ OK | Botões ocultos para mensagens apagadas     |
| ForwardMessageModal | ✅ OK | Corrigido: hooks movidos antes do early return |

---

## Conclusão

Implementação concluída. ForwardMessageModal corrigido.
