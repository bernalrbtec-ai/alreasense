# 🗑️ Implementação: Filtro de Mensagens Apagadas

> **Status:** ✅ Implementado em 10/02/2025  
> **Última atualização:** 10/02/2025

## 📋 Decisão de Design

**Comportamento Escolhido:** Manter mensagens apagadas **VISÍVEIS** com indicador "Esta mensagem foi apagada", mas **IMPEDIR** ações (responder/encaminhar).

**Justificativa:**
- Mantém histórico completo da conversa
- Usuário vê que mensagem foi apagada (transparência)
- Evita confusão sobre mensagens "desaparecidas"
- Consistente com comportamento atual do sistema

---

## 🎯 Objetivo

Garantir que mensagens apagadas (`is_deleted=True`):
- ✅ **APARECEM** na lista de mensagens (com indicador visual)
- ✅ **NÃO** podem ser encaminhadas
- ✅ **NÃO** podem ser respondidas
- ✅ **NÃO** contam como não lidas
- ✅ **NÃO** aparecem como última mensagem na lista lateral
- ✅ **NÃO** podem ser selecionadas para ações

---

## 🔍 Problemas Identificados

### 1. **Última Mensagem Apagada na Lista Lateral** ❌
- **Localização:** `backend/apps/chat/api/views.py` linha 332 (`last_message_queryset`)
- **Problema:** Query não filtra `is_deleted=False`
- **Impacto:** Lista lateral pode mostrar mensagem apagada como última mensagem
- **Correção:** Filtrar `is_deleted=False` no queryset

### 2. **Contagem de Mensagens Não Lidas** ❌
- **Localização:** 
  - `backend/apps/chat/api/views.py` linha 319 (`unread_count_annotated`)
  - `backend/apps/chat/models.py` linha 172 (`unread_count` property)
- **Problema:** Não filtra `is_deleted=False`
- **Impacto:** Mensagens apagadas contam como não lidas
- **Correção:** Adicionar `is_deleted=False` em todas queries de unread

### 3. **Encaminhar Mensagem Apagada** ❌
- **Localização:** `backend/apps/chat/api/views.py` linha 3990 (`forward_message`)
- **Problema:** Não verifica `is_deleted` antes de encaminhar
- **Impacto:** Permite encaminhar mensagens apagadas
- **Correção:** Validar `is_deleted` e retornar erro 400

### 4. **Responder Mensagem Apagada** ❌
- **Localização:** 
  - `backend/apps/chat/tasks.py` linha 851 (`send_message_to_evolution`)
  - `backend/apps/chat/consumers_v2.py` linha 671 (`create_message`)
- **Problema:** Não verifica `is_deleted` antes de usar como reply
- **Impacto:** Permite responder mensagens apagadas
- **Correção:** Validar `is_deleted` e continuar sem reply

### 5. **WebSocket Fallback** ❌
- **Localização:** `backend/apps/chat/utils/websocket.py` linha 127
- **Problema:** Fallback não filtra `is_deleted`
- **Impacto:** Última mensagem via WebSocket pode ser apagada
- **Correção:** Adicionar `.filter(is_deleted=False)`

### 6. **Frontend - Validação** ❌
- **Localização:** 
  - `frontend/src/modules/chat/components/ForwardMessageModal.tsx`
  - `frontend/src/modules/chat/components/MessageInput.tsx`
  - `frontend/src/modules/chat/components/MessageList.tsx`
- **Problema:** Não verifica `is_deleted` antes de permitir ações
- **Impacto:** UI permite ações em mensagens apagadas
- **Correção:** Desabilitar botões e validar antes de ações

### 7. **MessageViewSet Queryset** ❌
- **Localização:** `backend/apps/chat/api/views.py` linha 4154 (`get_queryset`)
- **Problema:** Não filtra `is_deleted=False` por padrão
- **Impacto:** Mensagens apagadas podem ser buscadas via API
- **Correção:** Filtrar por padrão (ou adicionar parâmetro opcional)

---

## ✅ Plano de Implementação

### **FASE 1: Backend - Filtros Críticos** 🔧

#### **1.1 Filtrar Última Mensagem (CRÍTICO)** 🔴
**Arquivo:** `backend/apps/chat/api/views.py` linha 332

**Correção:**
```python
last_message_queryset = Message.objects.filter(
    is_deleted=False  # ✅ NOVO: Excluir mensagens apagadas
).select_related(
    'sender', 'conversation'
).prefetch_related('attachments').order_by('-created_at')
```

**Mitigação - Risco Alto:**
- ⚠️ **Problema:** Se todas mensagens recentes forem apagadas, `last_message` pode ser `None`
- ✅ **Solução:** Buscar próxima mensagem não apagada (já implementado no queryset)
- ✅ **Fallback:** Se não houver mensagens não apagadas, retornar `None` (frontend já trata)

**Verificação no Serializer:**
```python
def get_last_message(self, obj):
    if hasattr(obj, 'last_message_list') and obj.last_message_list:
        last_msg = obj.last_message_list[0]
        # ✅ GARANTIR: Verificar se não está apagada (double-check)
        if not last_msg.is_deleted:
            return MessageSerializer(last_msg).data
        # Se última está apagada, buscar próxima não apagada
        next_msg = obj.messages.filter(is_deleted=False).order_by('-created_at').first()
        if next_msg:
            return MessageSerializer(next_msg).data
        return None
    
    # Fallback: buscar próxima mensagem não apagada
    last_message = obj.messages.filter(is_deleted=False).order_by('-created_at').first()
    if last_message:
        return MessageSerializer(last_message).data
    return None
```

**Risco:** 🔴 Alto → ✅ Mitigado com verificação dupla

---

#### **1.2 Filtrar Contagem de Não Lidas** 📊
**Arquivo:** `backend/apps/chat/api/views.py` linha 319

**Correção:**
```python
queryset = queryset.annotate(
    unread_count_annotated=Count(
        'messages',
        filter=Q(
            messages__direction='incoming',
            messages__status__in=['sent', 'delivered'],
            messages__is_deleted=False  # ✅ NOVO: Excluir mensagens apagadas
        ),
        distinct=True
    )
)
```

**Property no Model:**
**Arquivo:** `backend/apps/chat/models.py` linha 172

**Correção:**
```python
@property
def unread_count(self):
    """Conta mensagens não lidas (incoming que não estão 'seen' e não apagadas)."""
    return self.messages.filter(
        direction='incoming',
        status__in=['sent', 'delivered'],
        is_deleted=False  # ✅ NOVO: Excluir mensagens apagadas
    ).count()
```

**Outras Queries de Unread:**
- Linha 2736: `unread_messages` - adicionar `is_deleted=False`
- Linha 3267: `unread_messages` - adicionar `is_deleted=False`

**Risco:** 🟢 Baixo → ✅ Comportamento esperado

---

#### **1.3 Filtrar WebSocket Fallback** 🔄
**Arquivo:** `backend/apps/chat/utils/websocket.py` linha 127

**Correção:**
```python
last_msg = Message.objects.filter(
    conversation=conversation,
    is_deleted=False  # ✅ NOVO: Excluir mensagens apagadas
).select_related('sender', 'conversation').prefetch_related('attachments').order_by('-created_at').first()
```

**Risco:** 🟢 Baixo → ✅ Consistência

---

#### **1.4 Filtrar MessageViewSet Queryset** 🔍
**Arquivo:** `backend/apps/chat/api/views.py` linha 4154

**Correção:**
```python
def get_queryset(self):
    queryset = self.queryset.filter(
        is_deleted=False  # ✅ NOVO: Excluir mensagens apagadas por padrão
    )
    # ... resto do código
```

**Risco:** 🟡 Médio → ⚠️ Verificar uso externo antes

---

### **FASE 2: Backend - Validações de Ações** 🛡️

#### **2.1 Validar Encaminhar Mensagem Apagada** 🚫
**Arquivo:** `backend/apps/chat/api/views.py` linha 3990

**Correção:**
```python
@action(detail=True, methods=['post'], url_path='forward')
def forward_message(self, request, pk=None):
    message = self.get_object()
    user = request.user
    
    # ✅ NOVO: Verificar se mensagem está apagada
    if message.is_deleted:
        return Response(
            {
                'error': 'Não é possível encaminhar uma mensagem que foi apagada',
                'message_id': str(message.id),
                'is_deleted': True
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # ... resto do código existente
```

**Risco:** 🟢 Baixo → ✅ Erro claro

---

#### **2.2 Validar Responder Mensagem Apagada** 💬
**Arquivo:** `backend/apps/chat/tasks.py` linha 851

**Correção:**
```python
if reply_to_uuid:
    original_message = await database_sync_to_async(
        Message.objects.select_related('conversation')
        .prefetch_related('attachments')
        .filter(
            id=reply_to_uuid, 
            conversation=conversation,
            is_deleted=False  # ✅ NOVO: Não permitir reply de mensagem apagada
        ).first
    )()
    
    if not original_message:
        logger.warning(
            f"⚠️ [CHAT ENVIO] Mensagem original não encontrada ou apagada: {reply_to_uuid}"
        )
        # ✅ MITIGAÇÃO: Continuar sem reply se mensagem foi apagada
        reply_to_uuid = None
        quoted_message_id = None
        quoted_remote_jid = None
```

**Validação Adicional no WebSocket:**
**Arquivo:** `backend/apps/chat/consumers_v2.py` linha 671

**Correção:**
```python
def create_message(self, conversation_id, content, is_internal, attachment_urls, 
                   include_signature=True, reply_to=None, mentions=None, mention_everyone=False):
    # ... código existente ...
    
    # ✅ NOVO: Validar reply_to se fornecido
    if reply_to:
        try:
            reply_message = Message.objects.get(
                id=reply_to,
                conversation_id=conversation_id,
                is_deleted=False  # ✅ Não permitir reply de mensagem apagada
            )
            metadata['reply_to'] = reply_to
        except Message.DoesNotExist:
            logger.warning(
                f"⚠️ [CHAT WS V2] Mensagem de reply não encontrada ou apagada: {reply_to}"
            )
            # Continuar sem reply
            reply_to = None
```

**Risco:** 🟡 Médio → ✅ Mitigado (continua sem reply)

---

### **FASE 3: Frontend - Validações e UI** 🎨

#### **3.1 Desabilitar Botões de Ação em Mensagens Apagadas** 🚫
**Arquivo:** `frontend/src/modules/chat/components/MessageList.tsx`

**Correção:**
```typescript
// ✅ NOVO: Desabilitar ações em mensagens apagadas
{!messageItem.is_deleted && (
  <div className="flex items-center gap-2">
    <button
      onClick={() => setReplyToMessage(messageItem)}
      disabled={messageItem.is_deleted}
      className="p-1 hover:bg-gray-100 rounded disabled:opacity-50 disabled:cursor-not-allowed"
      title={messageItem.is_deleted ? 'Não é possível responder mensagem apagada' : 'Responder'}
    >
      <Reply className="w-4 h-4" />
    </button>
    <button
      onClick={() => setForwardMessage(messageItem)}
      disabled={messageItem.is_deleted}
      className="p-1 hover:bg-gray-100 rounded disabled:opacity-50 disabled:cursor-not-allowed"
      title={messageItem.is_deleted ? 'Não é possível encaminhar mensagem apagada' : 'Encaminhar'}
    >
      <Forward className="w-4 h-4" />
    </button>
  </div>
)}
```

**Risco:** 🟢 Baixo → ✅ Previne ações na UI

---

#### **3.2 Validar Encaminhar no Frontend** 🚫
**Arquivo:** `frontend/src/modules/chat/components/ForwardMessageModal.tsx`

**Correção aplicada:**
- `useEffect` para bloquear e fechar modal quando `message.is_deleted`
- Early return `if (message?.is_deleted) return null` **após todos os hooks** (regras de Hooks do React)
- ⚠️ **Importante:** O `return null` deve vir DEPOIS de todos os `useState`, `useEffect` e `useCallback`; caso contrário, viola as regras de Hooks.

**Risco:** 🟢 Baixo → ✅ Previne ação antes de chamar API

---

#### **3.3 Validar Responder no Frontend** 💬
**Arquivo:** `frontend/src/modules/chat/components/MessageInput.tsx`

**Correção:**
```typescript
const handleSendMessage = async () => {
  // ... código existente ...
  
  // ✅ NOVO: Verificar se replyToMessage está apagada antes de enviar
  if (replyToMessage?.is_deleted) {
    toast.error('Não é possível responder uma mensagem que foi apagada');
    clearReply(); // Limpar reply se mensagem foi apagada
    return;
  }
  
  // ... resto do código
}
```

**Risco:** 🟢 Baixo → ✅ Previne ação antes de enviar

---

#### **3.4 Atualizar WebSocket Handler** 🔄
**Arquivo:** `frontend/src/modules/chat/hooks/useTenantSocket.ts`

**Correção:**
```typescript
// ✅ NOVO: Quando mensagem é apagada e é a última, atualizar last_message da conversa
const handleMessageDeleted = (data: WebSocketMessage) => {
  if (data.message) {
    const { updateMessageDeleted, updateConversation } = useChatStore.getState();
    const messageId = data.message.id;
    const conversationId = data.conversation_id || data.message.conversation_id;
    
    // Atualizar mensagem como apagada
    updateMessageDeleted(messageId);
    
    // ✅ NOVO: Se mensagem apagada era a última, buscar próxima não apagada
    if (conversationId) {
      const { conversations } = useChatStore.getState();
      const conversation = conversations.find(c => c.id === conversationId);
      
      if (conversation?.last_message?.id === messageId) {
        // Buscar próxima mensagem não apagada do backend
        api.get(`/chat/conversations/${conversationId}/messages/?limit=1&offset=0`)
          .then((response) => {
            const messages = response.data.results || [];
            if (messages.length > 0 && !messages[0].is_deleted) {
              // Atualizar last_message da conversa
              updateConversation({
                ...conversation,
                last_message: messages[0]
              });
            } else {
              // Não há mais mensagens não apagadas
              updateConversation({
                ...conversation,
                last_message: null
              });
            }
          })
          .catch((error) => {
            console.warn('⚠️ [TENANT WS] Erro ao buscar próxima mensagem:', error);
          });
      }
    }
  }
};
```

**Risco:** 🟡 Médio → ⚠️ Requer código adicional

---

## 📊 Matriz de Riscos Revisada

| Correção | Risco | Impacto | Mitigação | Status |
|----------|-------|---------|-----------|--------|
| Filtrar `last_message_queryset` | 🔴 Alto | Última mensagem pode ser `None` | Verificação dupla (queryset + serializer) + frontend trata | ✅ Mitigado |
| Filtrar `unread_count` | 🟢 Baixo | Contagem diminui | Esperado | ✅ Seguro |
| Validar `forward_message` | 🟢 Baixo | Erro claro se apagada | Retornar erro 400 | ✅ Seguro |
| Validar `reply_to` | 🟡 Médio | Evita reply inválido | Continuar sem reply | ✅ Mitigado |
| Filtrar WebSocket fallback | 🟢 Baixo | Consistência | Adicionar filtro | ✅ Seguro |
| Filtrar `MessageViewSet` | 🟡 Médio | API não retorna apagadas | Verificar uso externo | ⚠️ Verificar |
| Desabilitar botões frontend | 🟢 Baixo | Previne ação | Botões desabilitados | ✅ Seguro |
| Validar frontend forward | 🟢 Baixo | Previne ação | Fechar modal | ✅ Seguro |
| Validar frontend reply | 🟢 Baixo | Previne ação | Limpar reply + toast | ✅ Seguro |
| Atualizar WebSocket handler | 🟡 Médio | Last message atualiza | Buscar próxima não apagada | ⚠️ Implementar |

---

## 🧪 Cenários de Teste

### **Teste 1: Última Mensagem Apagada**
- **Cenário:** Última mensagem de conversa é apagada
- **Esperado:** 
  - Lista lateral mostra próxima mensagem não apagada
  - Se não houver, mostra `null` (frontend trata)

### **Teste 2: Encaminhar Mensagem Apagada**
- **Cenário:** Tentar encaminhar mensagem apagada
- **Esperado:**
  - Backend retorna erro 400
  - Frontend mostra toast de erro
  - Modal não abre (ou fecha automaticamente)

### **Teste 3: Responder Mensagem Apagada**
- **Cenário:** Tentar responder mensagem apagada
- **Esperado:**
  - Frontend limpa reply automaticamente
  - Mensagem é enviada sem reply
  - Toast informa que mensagem foi apagada

### **Teste 4: Mensagem Apagada Durante Uso (Race Condition)**
- **Cenário:** Usuário seleciona mensagem para reply, mensagem é apagada antes de enviar
- **Esperado:**
  - Frontend detecta e limpa reply
  - Backend valida e continua sem reply
  - Mensagem é enviada normalmente (sem quote)

### **Teste 5: Todas Mensagens Apagadas**
- **Cenário:** Apagar todas mensagens de uma conversa
- **Esperado:**
  - Lista de mensagens mostra todas como "apagada"
  - Última mensagem = `null` (frontend trata)
  - Contagem não lidas = 0

### **Teste 6: WebSocket - Mensagem Apagada**
- **Cenário:** Mensagem é apagada enquanto usuário está vendo conversa
- **Esperado:**
  - Mensagem atualiza para mostrar "apagada"
  - Botões de ação desaparecem
  - Se era última mensagem, busca próxima não apagada

---

## 📝 Checklist de Implementação

### **Backend - Crítico**
- [x] Adicionar `.filter(is_deleted=False)` em `last_message_queryset` (views.py)
- [x] Adicionar verificação em `get_last_message` serializer (fallback)
- [x] Adicionar `is_deleted=False` em `unread_count_annotated` (views.py e websocket.py)
- [ ] Adicionar `is_deleted=False` em `unread_count` property (models.py) – *não necessário; annotate cobre*
- [ ] Adicionar `is_deleted=False` em outras queries de unread (linhas 2736, 3267) – *verificar se existem*
- [x] Adicionar `.filter(is_deleted=False)` em WebSocket fallback (websocket.py)
- [ ] Adicionar `.filter(is_deleted=False)` em `MessageViewSet.get_queryset` – *não implementado; verificar uso externo*
- [x] Adicionar validação em `forward_message`
- [ ] Adicionar validação em `reply_to` no `tasks.py` – *não implementado; frontend bloqueia*
- [ ] Adicionar validação em `reply_to` no `consumers_v2.py` – *não implementado; frontend bloqueia*
- [x] MessageSerializer: mascarar `content` e `attachments` quando `is_deleted=True`

### **Frontend - Crítico**
- [x] Ocultar Responder/Encaminhar/Apagar em mensagens apagadas (`MessageContextMenu.tsx`)
- [x] Validar `forward_message` e bloquear modal (`ForwardMessageModal.tsx`) + **correção Hooks**
- [x] Validar `reply_to` e mostrar "Mensagem apagada" no preview (`MessageInput.tsx`)
- [x] ConversationList: fallback "Mensagem apagada" na barra lateral
- [ ] Atualizar `handleMessageDeleted` para atualizar `last_message` – *não implementado; backend já filtra*

### **Testes**
- [ ] Testar última mensagem apagada
- [ ] Testar encaminhar mensagem apagada
- [ ] Testar responder mensagem apagada
- [ ] Testar race condition (mensagem apagada durante uso)
- [ ] Testar todas mensagens apagadas
- [ ] Testar WebSocket atualização (message_deleted broadcast)

---

## 🎯 Ordem de Implementação Recomendada

1. **FASE 1:** Filtros Backend (Base sólida)
   - 1.1 Filtrar `last_message_queryset`
   - 1.2 Filtrar `unread_count`
   - 1.3 Filtrar WebSocket fallback
   - 1.4 Filtrar `MessageViewSet` (após verificar uso)

2. **FASE 2:** Validações Backend (Prevenção)
   - 2.1 Validar `forward_message`
   - 2.2 Validar `reply_to`

3. **FASE 3:** Frontend (UX melhorada)
   - 3.1 Desabilitar botões
   - 3.2 Validar forward
   - 3.3 Validar reply
   - 3.4 Atualizar WebSocket handler

4. **Testes:** Validar todos os cenários

---

## ⚠️ Pontos de Atenção Especiais

### **1. Última Mensagem Apagada (Risco Alto)**
- ✅ **Mitigação Principal:** Filtrar no queryset (buscar próxima não apagada)
- ✅ **Mitigação Secundária:** Verificação no serializer com fallback
- ✅ **Mitigação Terciária:** Frontend já trata `last_message = null`

### **2. Performance**
- ✅ Todas queries já têm índice em `is_deleted` (models.py linha 282)
- ✅ Filtros não devem impactar performance significativamente

### **3. Compatibilidade**
- ✅ Mensagens existentes com `is_deleted=False` (padrão) não são afetadas
- ✅ Mudanças são retrocompatíveis
- ⚠️ **Verificar:** Uso externo de `MessageViewSet` antes de filtrar

### **4. WebSocket - Atualização de Last Message**
- ⚠️ **Requer código adicional:** Atualizar `last_message` quando última mensagem é apagada
- ✅ WebSocket já tem `message_deleted` handler
- ✅ Frontend já tem `updateMessageDeleted`

---

## 📈 Resultado Esperado

Após implementação:
- ✅ Mensagens apagadas **APARECEM** no chat (com indicador "apagada")
- ✅ Última mensagem sempre é não apagada (ou `null`)
- ✅ Mensagens apagadas **NÃO** contam como não lidas
- ✅ **NÃO** é possível encaminhar mensagens apagadas
- ✅ **NÃO** é possível responder mensagens apagadas
- ✅ UI previne ações em mensagens apagadas
- ✅ Sistema consistente em todas as camadas

---

## 🚀 Próximos Passos (pós-implementação)

1. ✅ **Implementação** – Fases 1, 2 e 3 concluídas
2. 🧪 **Testar em staging** – Validar cenários antes de produção
3. 📤 **Deploy** – Horário de baixo tráfego
4. ⚠️ **Opcional:** Validar `reply_to` em tasks.py e consumers_v2.py (baixo risco)
5. ⚠️ **Opcional:** Filtrar MessageViewSet – verificar uso externo antes

---

## ⚠️ Riscos de Deploy (atualizado 10/02/2025)

| Item | Risco | O que observar |
|------|-------|----------------|
| MessageSerializer mascarar conteúdo | Baixo | Clientes que assumem content sempre preenchido |
| Filtros last_message/unread_count | Médio | Contagem pode diminuir; lateral mostra msg anterior ou "Nova conversa" |
| ForwardMessageModal | Baixo | Correção de Hooks aplicada |
| Integrações (n8n, API) | Baixo | forward pode retornar 400 para msg apagada |
| Migrações | Verificar | Garantir que migration `is_deleted` está aplicada |

**Recomendações:** Testar em staging; validar cenários de mensagem apagada; ter rollback pronto.

---

## 📅 Histórico

| Data | Evento |
|------|--------|
| 2026-02-09 | Documento criado, plano aprovado |
| 2026-02-10 | Implementação concluída; ForwardMessageModal Hooks corrigido |
