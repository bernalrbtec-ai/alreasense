# Revisão da Implementação: Mensagens Apagadas

> **Status:** Implementado em 10/02/2025  
> **Documento relacionado:** [IMPLEMENTACAO_FILTRO_MENSAGENS_APAGADAS.md](./IMPLEMENTACAO_FILTRO_MENSAGENS_APAGADAS.md)

## Visão geral

A implementação cobre os requisitos:
- **Mostrar** que a mensagem foi apagada: "Mensagem apagada" / "Esta mensagem foi apagada"
- **Não exibir** o conteúdo em: barra lateral, reply, forward

---

## 📁 Arquivos alterados (referência rápida)

| Camada | Arquivo | Alteração |
|--------|---------|-----------|
| Backend | `api/serializers.py` | MessageSerializer mascarar content/attachments; get_last_message filtrar `is_deleted` |
| Backend | `api/views.py` | last_message_queryset, unread_count, forward_message |
| Backend | `utils/websocket.py` | last_message e unread_count filtram `is_deleted` |
| Frontend | `ConversationList.tsx` | Fallback "Mensagem apagada" na lateral |
| Frontend | `MessageInput.tsx` | Preview e bloqueio de reply |
| Frontend | `ForwardMessageModal.tsx` | Bloqueio + correção Hooks |
| Frontend | `MessageContextMenu.tsx` | Ocultar Responder/Encaminhar/Apagar |

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

## 🔍 Melhorias futuras (opcional)

| Item | Onde | Prioridade | Esforço |
|------|------|------------|---------|
| Validar `reply_to` em tasks.py e consumers_v2.py | Backend | Baixa | ~30 min |
| Filtrar MessageViewSet por `is_deleted` | Backend | Verificar uso externo antes | Variável |
| WebSocket handler no frontend para atualizar `last_message` ao apagar | useTenantSocket.ts | Baixa (backend já filtra) | ~1 h |

**Notas:**
- Ordenação da lista usa `last_message_at` da conversa; ao apagar a última msg, a conversa mantém posição — OK.
- Preview do ForwardMessageModal: mensagem apagada → modal fecha imediatamente; preview não é exibido.

---

## ⚠️ Riscos de deploy (resumo)

| Item | Risco |
|------|-------|
| Filtros last_message / unread_count | Médio — contagem pode mudar; lateral pode mostrar msg anterior |
| Integrações (n8n, API forward) | Baixo — forward retorna 400 para msg apagada |
| Migrações | Garantir migration `is_deleted` aplicada |

Recomendação: testar em staging; validar cenários de mensagem apagada antes de produção.

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

Implementação concluída. Requisitos atendidos:
- Usuário sabe que a mensagem foi apagada (indicador em todos os pontos)
- Conteúdo não é exibido em lateral, reply nem forward
- Ações bloqueadas (responder, encaminhar) em mensagens apagadas
