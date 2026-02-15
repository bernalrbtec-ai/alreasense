# 📋 Plano Completo: Correção de Mensagens Apagadas

## 🎯 Objetivo
Garantir que mensagens apagadas (`is_deleted=True`) não sejam:
- Exibidas na lista de mensagens do chat
- Usadas como última mensagem na lista lateral
- Encaminhadas ou respondidas
- Contadas como não lidas
- Selecionáveis para ações (responder/encaminhar)

---

## 🔍 Problemas Identificados

### 1. **Listar Mensagens no Chat** ❌
- **Localização:** `backend/apps/chat/api/views.py` linha 3351
- **Problema:** Query não filtra `is_deleted=False`
- **Impacto:** Mensagens apagadas aparecem na lista do chat

### 2. **Última Mensagem na Lista Lateral** ❌
- **Localização:** `backend/apps/chat/api/views.py` linha 332 (`last_message_queryset`)
- **Problema:** Query não filtra `is_deleted=False`
- **Impacto:** Lista lateral pode mostrar mensagem apagada como última mensagem

### 3. **Contagem de Mensagens Não Lidas** ❌
- **Localização:** 
  - `backend/apps/chat/api/views.py` linha 319 (`unread_count_annotated`)
  - `backend/apps/chat/models.py` linha 172 (`unread_count` property)
- **Problema:** Não filtra `is_deleted=False`
- **Impacto:** Mensagens apagadas contam como não lidas

### 4. **Encaminhar Mensagem Apagada** ❌
- **Localização:** `backend/apps/chat/api/views.py` linha 3990 (`forward_message`)
- **Problema:** Não verifica `is_deleted` antes de encaminhar
- **Impacto:** Permite encaminhar mensagens apagadas

### 5. **Responder Mensagem Apagada** ❌
- **Localização:** `backend/apps/chat/tasks.py` linha 851 (`send_message_to_evolution`)
- **Problema:** Não verifica `is_deleted` antes de usar como reply
- **Impacto:** Permite responder mensagens apagadas

### 6. **WebSocket Fallback** ❌
- **Localização:** `backend/apps/chat/utils/websocket.py` linha 127
- **Problema:** Fallback não filtra `is_deleted`
- **Impacto:** Última mensagem via WebSocket pode ser apagada

### 7. **Frontend - Validação** ❌
- **Localização:** 
  - `frontend/src/modules/chat/components/ForwardMessageModal.tsx`
  - `frontend/src/modules/chat/components/MessageInput.tsx`
- **Problema:** Não verifica `is_deleted` antes de permitir ações
- **Impacto:** UI permite ações em mensagens apagadas

### 8. **MessageViewSet Queryset** ❌
- **Localização:** `backend/apps/chat/api/views.py` linha 4154 (`get_queryset`)
- **Problema:** Não filtra `is_deleted=False`
- **Impacto:** Mensagens apagadas podem ser buscadas via API

---

## ✅ Plano de Correções

### **FASE 1: Backend - Filtros de Query** 🔧

#### **1.1 Filtrar Mensagens no Endpoint `messages`**
**Arquivo:** `backend/apps/chat/api/views.py` linha 3351

**Correção:**
```python
messages = Message.objects.filter(
    conversation=conversation,
    is_deleted=False  # ✅ NOVO: Excluir mensagens apagadas
).select_related(...)
```

**Mitigação:**
- ✅ Baixo risco - comportamento esperado
- ✅ Mensagens apagadas não devem aparecer no chat

**Contagem Total:**
```python
total_count = Message.objects.filter(
    conversation=conversation,
    is_deleted=False  # ✅ NOVO: Excluir mensagens apagadas na contagem
).count()
```

---

#### **1.2 Filtrar Última Mensagem (CRÍTICO)** 🔴
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
    
    # Fallback: buscar próxima mensagem não apagada
    last_message = obj.messages.filter(is_deleted=False).order_by('-created_at').first()
    if last_message:
        return MessageSerializer(last_message).data
    return None
```

---

#### **1.3 Filtrar Contagem de Não Lidas** 📊
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

**Mitigação:**
- ✅ Risco baixo - comportamento esperado
- ✅ Mensagens apagadas não devem contar como não lidas

**Outras Queries de Unread:**
- Linha 2736: `unread_messages` - adicionar `is_deleted=False`
- Linha 3267: `unread_messages` - adicionar `is_deleted=False`

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

**Mitigação:**
- ✅ Risco baixo - comportamento esperado
- ✅ Mensagens apagadas não devem ser acessíveis via API

---

#### **1.5 Filtrar WebSocket Fallback** 🔄
**Arquivo:** `backend/apps/chat/utils/websocket.py` linha 127

**Correção:**
```python
last_msg = Message.objects.filter(
    conversation=conversation,
    is_deleted=False  # ✅ NOVO: Excluir mensagens apagadas
).select_related('sender', 'conversation').prefetch_related('attachments').order_by('-created_at').first()
```

**Mitigação:**
- ✅ Risco baixo - consistência com outras queries

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
                'message_id': str(message.id)
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # ... resto do código existente
```

**Mitigação:**
- ✅ Risco baixo - retorna erro claro
- ✅ Frontend pode mostrar mensagem apropriada

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

**Mitigação:**
- ✅ Risco baixo - continua sem reply se mensagem foi apagada
- ✅ Evita erro e permite enviar mensagem normalmente

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

---

### **FASE 3: Frontend - Validações e UI** 🎨

#### **3.1 Validar Encaminhar no Frontend** 🚫
**Arquivo:** `frontend/src/modules/chat/components/ForwardMessageModal.tsx`

**Correção:**
```typescript
export function ForwardMessageModal({ message, onClose, onSuccess }: ForwardMessageModalProps) {
  // ✅ NOVO: Verificar se mensagem está apagada
  useEffect(() => {
    if (message.is_deleted) {
      toast.error('Não é possível encaminhar uma mensagem que foi apagada');
      onClose();
    }
  }, [message.is_deleted, onClose]);

  // ✅ NOVO: Desabilitar botão se mensagem está apagada
  if (message.is_deleted) {
    return (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50" onClick={onClose}>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-md">
          <div className="flex items-center gap-3 text-red-600">
            <AlertCircle className="w-6 h-6" />
            <div>
              <h3 className="font-semibold">Mensagem Apagada</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Não é possível encaminhar uma mensagem que foi apagada.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="mt-4 w-full px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded-lg"
          >
            Fechar
          </button>
        </div>
      </div>
    );
  }

  // ... resto do código normal
}
```

**Mitigação:**
- ✅ Risco baixo - previne ação antes de chamar API
- ✅ Melhor UX - mostra mensagem clara

---

#### **3.2 Validar Responder no Frontend** 💬
**Arquivo:** `frontend/src/modules/chat/components/MessageInput.tsx`

**Correção:**
```typescript
// ✅ NOVO: Verificar se replyToMessage está apagada antes de enviar
const handleSendMessage = async () => {
  // ... código existente ...
  
  if (replyToMessage?.is_deleted) {
    toast.error('Não é possível responder uma mensagem que foi apagada');
    clearReply(); // Limpar reply se mensagem foi apagada
    return;
  }
  
  // ... resto do código
}
```

**Mitigação:**
- ✅ Risco baixo - previne ação antes de enviar
- ✅ Limpa reply automaticamente se mensagem foi apagada

---

#### **3.3 Desabilitar Botões de Ação em Mensagens Apagadas** 🚫
**Arquivo:** `frontend/src/modules/chat/components/MessageList.tsx`

**Correção:**
```typescript
// ✅ NOVO: Desabilitar ações em mensagens apagadas
{!message.is_deleted && (
  <div className="flex items-center gap-2">
    <button
      onClick={() => setReplyToMessage(message)}
      disabled={message.is_deleted}
      className="p-1 hover:bg-gray-100 rounded"
      title={message.is_deleted ? 'Não é possível responder mensagem apagada' : 'Responder'}
    >
      <Reply className="w-4 h-4" />
    </button>
    <button
      onClick={() => setForwardMessage(message)}
      disabled={message.is_deleted}
      className="p-1 hover:bg-gray-100 rounded"
      title={message.is_deleted ? 'Não é possível encaminhar mensagem apagada' : 'Encaminhar'}
    >
      <Forward className="w-4 h-4" />
    </button>
  </div>
)}
```

**Mitigação:**
- ✅ Risco baixo - previne ações na UI
- ✅ Melhor UX - botões desabilitados com tooltip explicativo

---

## 📊 Matriz de Riscos e Mitigações (REVISADA)

### ⚠️ **ANÁLISE CRÍTICA DO CÓDIGO EXISTENTE**

**Descobertas Importantes:**
1. ✅ Frontend **JÁ** mostra mensagens apagadas com "Esta mensagem foi apagada" (MessageList.tsx linha 906-912)
2. ✅ Frontend **JÁ** esconde conteúdo/anexos quando `is_deleted=true` (linha 929, 948)
3. ✅ WebSocket **JÁ** tem `message_deleted` handler (useChatSocket.ts linha 237)
4. ✅ Store **JÁ** tem `updateMessageDeleted` (chatStore.ts linha 513)
5. ❌ **PROBLEMA:** Backend ainda retorna mensagens apagadas nas queries

**Decisão de Design Necessária:**
- **Opção A:** Filtrar completamente (mensagens apagadas não aparecem)
- **Opção B:** Mostrar como "apagada" (comportamento atual do frontend)

**Recomendação:** **Opção A** (filtrar completamente) - mais consistente com WhatsApp

---

| Correção | Risco | Impacto Real | Mitigação | Status |
|----------|-------|---------------|-----------|--------|
| **1. Filtrar `messages` endpoint** | 🟡 **MÉDIO** | **Mudança de comportamento:** Mensagens apagadas desaparecem completamente (antes apareciam como "apagada") | ✅ Esperado - WhatsApp não mostra mensagens apagadas | ⚠️ **Requer decisão** |
| **2. Filtrar `last_message_queryset`** | 🔴 **ALTO** | **Última mensagem pode ser `None`:** Se todas mensagens recentes forem apagadas | ✅ Buscar próxima não apagada + fallback no serializer + frontend já trata `null` | ⚠️ **Requer atenção** |
| **3. Filtrar `unread_count`** | 🟢 **BAIXO** | **Contagem diminui:** Mensagens apagadas não contam como não lidas | ✅ Esperado - comportamento correto | ✅ **Seguro** |
| **4. Validar `forward_message`** | 🟢 **BAIXO** | **Erro claro:** Retorna 400 se mensagem apagada | ✅ Erro claro + frontend trata | ✅ **Seguro** |
| **5. Validar `reply_to`** | 🟡 **MÉDIO** | **Reply pode falhar silenciosamente:** Se mensagem foi apagada após selecionar | ✅ Validar antes de usar + continuar sem reply | ⚠️ **Requer atenção** |
| **6. Filtrar WebSocket fallback** | 🟢 **BAIXO** | **Consistência:** Última mensagem via WebSocket não será apagada | ✅ Adicionar filtro | ✅ **Seguro** |
| **7. Filtrar `MessageViewSet` queryset** | 🟡 **MÉDIO** | **API não retorna apagadas:** Mudança de comportamento da API | ✅ Esperado - mensagens apagadas não devem ser acessíveis | ⚠️ **Requer atenção** |
| **8. Validar frontend forward** | 🟢 **BAIXO** | **Previne ação:** Modal fecha se mensagem apagada | ✅ Mostrar erro + fechar modal | ✅ **Seguro** |
| **9. Validar frontend reply** | 🟡 **MÉDIO** | **Reply pode ser limpo:** Se mensagem foi apagada após selecionar | ✅ Limpar reply + toast informativo | ⚠️ **Requer atenção** |

---

## 🔴 **RISCOS CRÍTICOS REVISADOS**

### **RISCO 1: Mudança de Comportamento Visual** 🔴 **ALTO**
**Problema:** 
- Frontend **atualmente** mostra mensagens apagadas como "Esta mensagem foi apagada"
- Se filtrarmos no backend, essas mensagens **desaparecerão completamente**
- Usuários podem notar diferença de comportamento

**Impacto:**
- Mensagens que antes apareciam como "apagada" agora não aparecem
- Pode confundir usuários acostumados ao comportamento atual
- Histórico pode parecer incompleto

**Mitigação:**
- ✅ **Decisão:** Filtrar completamente (comportamento WhatsApp)
- ✅ **Comunicação:** Se necessário, avisar usuários sobre mudança
- ✅ **Frontend:** Remover código que mostra "apagada" (não será mais necessário)

**Decisão Necessária:** ✅ **Aprovar filtro completo** (recomendado)

---

### **RISCO 2: Última Mensagem Apagada** 🔴 **ALTO**
**Problema:**
- Se todas mensagens recentes forem apagadas, `last_message` pode ser `None`
- Lista lateral pode não mostrar preview

**Impacto:**
- Conversas podem aparecer sem preview na lista lateral
- Ordenação pode ser afetada
- Frontend pode mostrar "Carregando última mensagem..." indefinidamente

**Mitigação Múltipla (3 camadas):**
1. ✅ **Camada 1:** Filtrar no queryset (buscar próxima não apagada)
2. ✅ **Camada 2:** Verificação no serializer com fallback
3. ✅ **Camada 3:** Frontend já trata `last_message = null` (linha 519-532 ConversationList.tsx)

**Código de Mitigação:**
```python
# Serializer - get_last_message
def get_last_message(self, obj):
    if hasattr(obj, 'last_message_list') and obj.last_message_list:
        last_msg = obj.last_message_list[0]
        # ✅ VERIFICAÇÃO: Se última mensagem está apagada, buscar próxima
        if last_msg.is_deleted:
            last_msg = obj.messages.filter(is_deleted=False).order_by('-created_at').first()
            if last_msg:
                return MessageSerializer(last_msg).data
            return None
        return MessageSerializer(last_msg).data
    
    # Fallback: buscar próxima mensagem não apagada
    last_message = obj.messages.filter(is_deleted=False).order_by('-created_at').first()
    if last_message:
        return MessageSerializer(last_message).data
    return None
```

**Status:** ⚠️ **Mitigado com 3 camadas** - Risco reduzido para médio

---

### **RISCO 3: Race Condition - Reply Apagado** 🟡 **MÉDIO**
**Problema:**
- Usuário seleciona mensagem para reply
- Mensagem é apagada antes de enviar
- Reply pode falhar ou enviar sem quote

**Impacto:**
- Mensagem pode ser enviada sem quote (confuso)
- Ou pode falhar silenciosamente

**Mitigação:**
- ✅ **Backend:** Validar `is_deleted` antes de usar como reply
- ✅ **Frontend:** Validar antes de enviar + limpar reply se apagada
- ✅ **Comportamento:** Continuar sem reply se mensagem foi apagada

**Status:** ⚠️ **Mitigado** - Risco reduzido para baixo

---

### **RISCO 4: Performance - Queries Adicionais** 🟡 **MÉDIO**
**Problema:**
- Filtros `is_deleted=False` adicionam condições às queries
- Pode impactar performance em conversas com muitas mensagens

**Impacto:**
- Queries podem ser mais lentas
- Índices podem não ser suficientes

**Mitigação:**
- ✅ **Verificado:** Índice já existe em `is_deleted` (models.py linha 282)
- ✅ **Otimização:** Filtro usa índice existente
- ✅ **Monitoramento:** Verificar performance após deploy

**Status:** ✅ **Mitigado** - Risco baixo (índice existe)

---

### **RISCO 5: Compatibilidade - API Breaking Change** 🟡 **MÉDIO**
**Problema:**
- `MessageViewSet` não retornará mais mensagens apagadas
- Código externo pode depender desse comportamento

**Impacto:**
- Integrações podem quebrar
- Scripts podem não encontrar mensagens apagadas

**Mitigação:**
- ✅ **Verificação:** Buscar uso de `MessageViewSet` em código externo
- ✅ **Documentação:** Documentar mudança de comportamento
- ✅ **Versionamento:** Se necessário, adicionar parâmetro `include_deleted=false`

**Status:** ⚠️ **Requer verificação** - Risco médio

---

### **RISCO 6: WebSocket - Atualização de Last Message** 🟡 **MÉDIO**
**Problema:**
- Quando mensagem é apagada via WebSocket, `last_message` pode precisar atualizar
- Se última mensagem foi apagada, precisa buscar próxima

**Impacto:**
- Lista lateral pode não atualizar corretamente
- Preview pode ficar desatualizado

**Mitigação:**
- ✅ **WebSocket:** `broadcast_message_deleted` já existe
- ✅ **Frontend:** `updateMessageDeleted` atualiza store
- ✅ **Adicional:** Atualizar `last_message` da conversa quando última mensagem é apagada

**Código Adicional Necessário:**
```python
# Em broadcast_message_deleted ou handle_message_delete
# Se última mensagem foi apagada, atualizar last_message da conversa
if message.id == conversation.last_message_list[0].id if hasattr(conversation, 'last_message_list') else None:
    # Buscar próxima mensagem não apagada
    next_message = Message.objects.filter(
        conversation=conversation,
        is_deleted=False
    ).order_by('-created_at').first()
    
    # Atualizar conversation.last_message_list
    conversation.last_message_list = [next_message] if next_message else []
    
    # Broadcast conversation_updated para atualizar lista lateral
    broadcast_conversation_updated(conversation)
```

**Status:** ⚠️ **Requer código adicional** - Risco médio

---

## 🎯 **RISCOS REVISADOS - RESUMO FINAL**

| # | Risco | Severidade | Probabilidade | Mitigação | Status Final |
|---|-------|------------|---------------|-----------|--------------|
| 1 | Mudança comportamento visual | 🔴 Alto | Alta | Decisão + comunicação | ⚠️ **Aprovar** |
| 2 | Última mensagem `None` | 🔴 Alto | Média | 3 camadas de mitigação | ✅ **Mitigado** |
| 3 | Race condition reply | 🟡 Médio | Baixa | Validação backend + frontend | ✅ **Mitigado** |
| 4 | Performance queries | 🟡 Médio | Baixa | Índice existe | ✅ **Mitigado** |
| 5 | API breaking change | 🟡 Médio | Baixa | Verificar uso externo | ⚠️ **Verificar** |
| 6 | WebSocket last_message | 🟡 Médio | Média | Código adicional necessário | ⚠️ **Implementar** |

---

## ✅ **DECISÕES NECESSÁRIAS**

### **Decisão 1: Comportamento Visual** ⚠️ **CRÍTICA**
**Pergunta:** Mensagens apagadas devem:
- **A)** Desaparecer completamente (como WhatsApp) ✅ **RECOMENDADO**
- **B)** Aparecer como "Esta mensagem foi apagada" (comportamento atual)

**Recomendação:** **Opção A** - Filtrar completamente
- Mais consistente com WhatsApp
- Melhor UX (não polui histórico)
- Remove necessidade de mostrar "apagada"

**Ação:** Remover código frontend que mostra "apagada" após filtrar no backend

---

### **Decisão 2: API - Parâmetro Opcional** ⚠️ **OPCIONAL**
**Pergunta:** `MessageViewSet` deve ter parâmetro `include_deleted`?

**Recomendação:** **Não necessário inicialmente**
- Se houver necessidade futura, adicionar depois
- Simplifica implementação inicial

---

## 📋 **PLANO REVISADO COM MITIGAÇÕES**

### **FASE 1: Backend - Filtros (COM MITIGAÇÕES)**

#### **1.1 Filtrar Mensagens no Endpoint** ✅
- Adicionar `.filter(is_deleted=False)`
- **Risco:** Mudança de comportamento visual
- **Mitigação:** Decisão aprovada (filtrar completamente)

#### **1.2 Filtrar Última Mensagem** ⚠️ **CRÍTICO**
- Adicionar `.filter(is_deleted=False)` no queryset
- **Adicional:** Verificação no serializer com fallback
- **Adicional:** Atualizar WebSocket quando última mensagem é apagada
- **Risco:** `last_message = None`
- **Mitigação:** 3 camadas (queryset + serializer + frontend)

#### **1.3 Filtrar Unread Count** ✅
- Adicionar `is_deleted=False` em todas queries
- **Risco:** Baixo
- **Mitigação:** Comportamento esperado

#### **1.4 Filtrar MessageViewSet** ⚠️
- Adicionar `.filter(is_deleted=False)` no queryset
- **Risco:** API breaking change
- **Mitigação:** Verificar uso externo antes

#### **1.5 Filtrar WebSocket Fallback** ✅
- Adicionar `.filter(is_deleted=False)`
- **Risco:** Baixo
- **Mitigação:** Consistência

#### **1.6 Atualizar Last Message no WebSocket** ⚠️ **NOVO**
- Quando mensagem apagada é a última, buscar próxima
- Broadcast `conversation_updated`
- **Risco:** Lista lateral desatualizada
- **Mitigação:** Código adicional necessário

---

### **FASE 2: Backend - Validações**

#### **2.1 Validar Forward** ✅
- Verificar `is_deleted` antes de encaminhar
- **Risco:** Baixo
- **Mitigação:** Erro claro

#### **2.2 Validar Reply** ⚠️
- Validar antes de usar como reply
- Continuar sem reply se apagada
- **Risco:** Race condition
- **Mitigação:** Validação backend + frontend

---

### **FASE 3: Frontend**

#### **3.1 Remover Código "Mensagem Apagada"** ⚠️ **NOVO**
- Remover renderização de "Esta mensagem foi apagada"
- Mensagens apagadas não aparecerão mais
- **Risco:** Mudança visual
- **Mitigação:** Decisão aprovada

#### **3.2 Validar Forward** ✅
- Verificar antes de abrir modal
- **Risco:** Baixo

#### **3.3 Validar Reply** ⚠️
- Verificar antes de enviar
- Limpar reply se apagada
- **Risco:** Race condition
- **Mitigação:** Validação dupla

---

## 🚨 **RISCOS ADICIONAIS IDENTIFICADOS**

### **RISCO 7: Mensagens Apagadas em Cache** 🟡 **MÉDIO**
**Problema:**
- Frontend pode ter mensagens apagadas em cache (Zustand store)
- Ao filtrar no backend, cache pode ficar inconsistente

**Impacto:**
- Mensagens apagadas podem aparecer temporariamente
- Cache pode ter dados desatualizados

**Mitigação:**
- ✅ **WebSocket:** `message_deleted` já atualiza store
- ✅ **Adicional:** Filtrar mensagens apagadas ao buscar do backend
- ✅ **Adicional:** Limpar mensagens apagadas do cache após filtrar

**Código Adicional:**
```typescript
// Em fetchMessages ou setMessages
const messagesFiltered = messages.filter(msg => !msg.is_deleted);
setMessages(messagesFiltered, conversationId);
```

**Status:** ⚠️ **Requer código adicional** - Risco médio

---

### **RISCO 8: Paginação Quebrada** 🟡 **MÉDIO**
**Problema:**
- Se mensagens apagadas são filtradas, contagem total muda
- Paginação pode mostrar menos páginas do que esperado

**Impacto:**
- `has_more` pode estar incorreto
- Usuário pode não conseguir ver todas mensagens

**Mitigação:**
- ✅ **Contagem:** Já filtra `is_deleted=False` na contagem
- ✅ **Verificação:** Testar paginação com mensagens apagadas

**Status:** ✅ **Mitigado** - Risco baixo

---

## 📊 **MATRIZ FINAL DE RISCOS**

| Risco | Severidade | Probabilidade | Impacto | Mitigação | Status |
|-------|------------|---------------|---------|-----------|--------|
| Mudança visual | 🔴 Alto | Alta | Alto | Decisão + remover código | ⚠️ Aprovar |
| Last message None | 🔴 Alto | Média | Alto | 3 camadas | ✅ Mitigado |
| Race condition reply | 🟡 Médio | Baixa | Médio | Validação dupla | ✅ Mitigado |
| Performance | 🟡 Médio | Baixa | Baixo | Índice existe | ✅ Mitigado |
| API breaking | 🟡 Médio | Baixa | Médio | Verificar uso | ⚠️ Verificar |
| WebSocket update | 🟡 Médio | Média | Médio | Código adicional | ⚠️ Implementar |
| Cache inconsistente | 🟡 Médio | Média | Médio | Filtrar no frontend | ⚠️ Implementar |
| Paginação | 🟢 Baixo | Baixa | Baixo | Contagem correta | ✅ Mitigado |

---

## ✅ **CHECKLIST REVISADO**

### **Backend - Crítico**
- [ ] Filtrar `messages` endpoint (linha 3351)
- [ ] Filtrar `last_message_queryset` (linha 332) + **verificação no serializer**
- [ ] Filtrar `unread_count` (linhas 319, 172, 2736, 3267)
- [ ] Filtrar `MessageViewSet` queryset (linha 4154) + **verificar uso externo**
- [ ] Filtrar WebSocket fallback (linha 127)
- [ ] **NOVO:** Atualizar `last_message` quando última mensagem é apagada (WebSocket)
- [ ] Validar `forward_message` (linha 4017)
- [ ] Validar `reply_to` no tasks.py (linha 865)
- [ ] Validar `reply_to` no consumers_v2.py (linha 671)

### **Frontend - Crítico**
- [ ] **NOVO:** Remover renderização "Mensagem apagada" (MessageList.tsx linha 906-912)
- [ ] **NOVO:** Filtrar mensagens apagadas ao buscar do backend (fetchMessages)
- [ ] Validar `forward_message` antes de abrir modal
- [ ] Validar `reply_to` antes de enviar
- [ ] Desabilitar botões de ação em mensagens apagadas

### **Testes - Crítico**
- [ ] Conversa com todas mensagens apagadas
- [ ] Última mensagem apagada (verificar lista lateral)
- [ ] Encaminhar mensagem apagada
- [ ] Responder mensagem apagada
- [ ] Mensagem apagada durante uso (race condition)
- [ ] WebSocket atualiza last_message quando última é apagada
- [ ] Paginação com mensagens apagadas

---

## 🧪 Cenários de Teste

### **Teste 1: Conversa com Todas Mensagens Apagadas**
- **Cenário:** Apagar todas mensagens de uma conversa
- **Esperado:** 
  - Lista de mensagens vazia
  - Última mensagem = `None` (frontend trata)
  - Contagem não lidas = 0

### **Teste 2: Encaminhar Mensagem Apagada**
- **Cenário:** Tentar encaminhar mensagem apagada
- **Esperado:**
  - Backend retorna erro 400
  - Frontend mostra mensagem de erro
  - Modal fecha automaticamente

### **Teste 3: Responder Mensagem Apagada**
- **Cenário:** Tentar responder mensagem apagada
- **Esperado:**
  - Frontend limpa reply automaticamente
  - Mensagem é enviada sem reply
  - Toast informa que mensagem foi apagada

### **Teste 4: Última Mensagem Apagada**
- **Cenário:** Última mensagem de conversa é apagada
- **Esperado:**
  - Lista lateral mostra próxima mensagem não apagada
  - Se não houver, mostra `None` (frontend trata)

### **Teste 5: Mensagem Apagada em Lista**
- **Cenário:** Mensagem é apagada enquanto usuário está vendo conversa
- **Esperado:**
  - Mensagem desaparece da lista via WebSocket
  - Botões de ação desaparecem
  - Contagem atualiza automaticamente

---

## 📝 Checklist de Implementação

### **Backend**
- [ ] Adicionar `.filter(is_deleted=False)` em `messages` endpoint (linha 3351)
- [ ] Adicionar `.filter(is_deleted=False)` em `last_message_queryset` (linha 332)
- [ ] Adicionar verificação em `get_last_message` serializer (fallback)
- [ ] Adicionar `is_deleted=False` em `unread_count_annotated` (linha 319)
- [ ] Adicionar `is_deleted=False` em `unread_count` property (linha 172)
- [ ] Adicionar `is_deleted=False` em outras queries de unread (linhas 2736, 3267)
- [ ] Adicionar `.filter(is_deleted=False)` em `MessageViewSet.get_queryset` (linha 4154)
- [ ] Adicionar `.filter(is_deleted=False)` em WebSocket fallback (linha 127)
- [ ] Adicionar validação em `forward_message` (linha 4017)
- [ ] Adicionar validação em `reply_to` no `tasks.py` (linha 865)
- [ ] Adicionar validação em `reply_to` no `consumers_v2.py` (linha 671)

### **Frontend**
- [ ] Adicionar verificação em `ForwardMessageModal` (verificar `is_deleted`)
- [ ] Adicionar verificação em `MessageInput` (verificar `replyToMessage.is_deleted`)
- [ ] Desabilitar botões de ação em mensagens apagadas (`MessageList`)
- [ ] Adicionar tooltips explicativos
- [ ] Adicionar toast de erro quando necessário

### **Testes**
- [ ] Testar conversa com todas mensagens apagadas
- [ ] Testar encaminhar mensagem apagada
- [ ] Testar responder mensagem apagada
- [ ] Testar última mensagem apagada
- [ ] Testar atualização via WebSocket

---

## 🎯 Ordem de Implementação Recomendada

1. **FASE 1.1-1.5:** Filtros de Query (Backend) - Base sólida
2. **FASE 2.1-2.2:** Validações de Ações (Backend) - Prevenção
3. **FASE 3.1-3.3:** Validações Frontend - UX melhorada
4. **Testes:** Validar todos os cenários

---

## ⚠️ Pontos de Atenção Especiais

### **1. Última Mensagem Apagada (Risco Alto)**
- ✅ **Mitigação Principal:** Buscar próxima mensagem não apagada no queryset
- ✅ **Mitigação Secundária:** Verificação no serializer com fallback
- ✅ **Mitigação Terciária:** Frontend já trata `last_message = null`

### **2. Performance**
- ✅ Todas queries já têm índice em `is_deleted` (linha 282 do models.py)
- ✅ Filtros não devem impactar performance significativamente

### **3. Compatibilidade**
- ✅ Mensagens existentes com `is_deleted=False` (padrão) não são afetadas
- ✅ Mudanças são retrocompatíveis

---

## 📈 Resultado Esperado

Após implementação:
- ✅ Mensagens apagadas não aparecem no chat
- ✅ Última mensagem sempre é não apagada (ou `None`)
- ✅ Mensagens apagadas não contam como não lidas
- ✅ Não é possível encaminhar mensagens apagadas
- ✅ Não é possível responder mensagens apagadas
- ✅ UI previne ações em mensagens apagadas
- ✅ Sistema consistente em todas as camadas
