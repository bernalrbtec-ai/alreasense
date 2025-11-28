# 🗑️ Implementação: Mensagens Apagadas (Deleted Messages)

## 📊 Análise de Complexidade

### ✅ **Tratar Mensagens Apagadas Recebidas** - **MAIS FÁCIL** ⭐
- **Complexidade:** Baixa
- **Tempo estimado:** 1-2 horas
- **O que precisa:**
  - Processar webhook `messages.delete` da Evolution API
  - Adicionar campo `is_deleted` ou status `deleted` no modelo Message
  - Atualizar frontend para mostrar "Mensagem apagada"
  - Broadcast via WebSocket quando mensagem é apagada

### ⚙️ **Encaminhar Mensagem** - Média
- **Complexidade:** Média
- **Tempo estimado:** 3-4 horas
- **O que precisa:**
  - UI para selecionar conversa destino
  - Endpoint para forward via Evolution API
  - Gerenciar anexos ao encaminhar
  - Estado de seleção de conversa no frontend

### 🗑️ **Apagar Mensagem da Aplicação** - Média
- **Complexidade:** Média
- **Tempo estimado:** 2-3 horas
- **O que precisa:**
  - Endpoint DELETE para mensagem
  - Enviar comando para Evolution API
  - UI para botão de apagar
  - Validações (apenas próprias mensagens, etc)

## 🎯 Recomendação: Tratar Mensagens Apagadas Recebidas

**Por quê?**
1. ✅ Mais simples - só processar webhook existente
2. ✅ Evolution API já envia o evento
3. ✅ Não precisa criar UI complexa
4. ✅ Frontend só precisa mostrar visual diferente
5. ✅ Melhora UX imediatamente (usuário vê que mensagem foi apagada)

## 📋 Plano de Implementação

### 1️⃣ **Backend - Modelo Message**

Adicionar campo `is_deleted`:
```python
# backend/apps/chat/models.py
is_deleted = models.BooleanField(
    default=False,
    db_index=True,
    verbose_name='Mensagem Apagada',
    help_text='True se mensagem foi apagada no WhatsApp'
)
deleted_at = models.DateTimeField(
    null=True,
    blank=True,
    verbose_name='Data de Exclusão',
    help_text='Timestamp quando mensagem foi apagada'
)
```

### 2️⃣ **Backend - Webhook Handler**

Processar evento `messages.delete`:
```python
# backend/apps/chat/webhooks.py

@api_view(['POST'])
@permission_classes([AllowAny])
def evolution_webhook(request):
    event = request.data.get('event')
    
    if event == 'messages.delete':
        handle_message_delete(request.data, tenant, connection, wa_instance)
        return Response({'status': 'ok'})
    
    # ... outros eventos ...

def handle_message_delete(data, tenant, connection=None, wa_instance=None):
    """
    Processa mensagem apagada recebida do WhatsApp.
    
    Evolution API envia:
    {
        "event": "messages.delete",
        "instance": "instance_name",
        "data": {
            "key": {
                "remoteJid": "5517999999999@s.whatsapp.net",
                "fromMe": false,
                "id": "message_id_evolution"
            }
        }
    }
    """
    try:
        delete_data = data.get('data', {})
        key = delete_data.get('key', {})
        message_id_evolution = key.get('id')
        remote_jid = key.get('remoteJid')
        from_me = key.get('fromMe', False)
        
        if not message_id_evolution:
            logger.warning("⚠️ [WEBHOOK DELETE] message_id não fornecido")
            return
        
        # Buscar mensagem no banco
        message = Message.objects.filter(
            message_id=message_id_evolution,
            conversation__tenant=tenant
        ).first()
        
        if not message:
            logger.warning(f"⚠️ [WEBHOOK DELETE] Mensagem não encontrada: {message_id_evolution}")
            return
        
        # Marcar como apagada
        message.is_deleted = True
        message.deleted_at = timezone.now()
        message.save(update_fields=['is_deleted', 'deleted_at'])
        
        logger.info(f"✅ [WEBHOOK DELETE] Mensagem marcada como apagada: {message.id}")
        
        # Broadcast via WebSocket
        from apps.chat.utils.websocket import broadcast_message_deleted
        broadcast_message_deleted(message)
        
    except Exception as e:
        logger.error(f"❌ [WEBHOOK DELETE] Erro: {e}", exc_info=True)
```

### 3️⃣ **Backend - WebSocket Broadcast**

Adicionar função de broadcast:
```python
# backend/apps/chat/utils/websocket.py

def broadcast_message_deleted(message):
    """
    Broadcast quando mensagem é apagada.
    """
    from apps.chat.utils.serialization import serialize_message_for_ws
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    channel_layer = get_channel_layer()
    conversation = message.conversation
    
    room_group_name = f"chat_tenant_{conversation.tenant_id}_conversation_{conversation.id}"
    tenant_group = f"chat_tenant_{conversation.tenant_id}"
    
    message_data = serialize_message_for_ws(message)
    
    # Broadcast para conversa específica
    async_to_sync(channel_layer.group_send)(
        room_group_name,
        {
            'type': 'message_deleted',
            'message': message_data
        }
    )
    
    # Broadcast para tenant (atualizar lista de conversas)
    async_to_sync(channel_layer.group_send)(
        tenant_group,
        {
            'type': 'message_deleted',
            'message': message_data,
            'conversation_id': str(conversation.id)
        }
    )
```

### 4️⃣ **Frontend - Store (Zustand)**

Atualizar store para processar `message_deleted`:
```typescript
// frontend/src/modules/chat/store/chatStore.ts

// Adicionar action
updateMessageDeleted: (messageId: string) => set((state) => {
  // Atualizar na lista de mensagens
  const updatedMessages = state.activeConversation?.messages.map(msg =>
    msg.id === messageId
      ? { ...msg, is_deleted: true, deleted_at: new Date().toISOString() }
      : msg
  ) || [];
  
  // Atualizar activeConversation
  const updatedActiveConversation = state.activeConversation
    ? {
        ...state.activeConversation,
        messages: updatedMessages
      }
    : null;
  
  return {
    activeConversation: updatedActiveConversation
  };
}),
```

### 5️⃣ **Frontend - WebSocket Handler**

Processar evento `message_deleted`:
```typescript
// frontend/src/modules/chat/hooks/useChatSocket.ts

// No handleMessageReceived ou criar handleMessageDeleted
const handleMessageDeleted = (data: WebSocketMessage) => {
  if (data.message) {
    const { updateMessageDeleted } = useChatStore.getState();
    updateMessageDeleted(data.message.id);
  }
};

// Adicionar no switch do WebSocket
case 'message_deleted':
  handleMessageDeleted(data);
  break;
```

### 6️⃣ **Frontend - UI Component**

Mostrar "Mensagem apagada" no MessageList:
```typescript
// frontend/src/modules/chat/components/MessageList.tsx

{msg.is_deleted ? (
  <div className="flex items-center gap-2 text-gray-400 italic text-sm py-2">
    <Trash2 className="w-4 h-4" />
    <span>Esta mensagem foi apagada</span>
  </div>
) : (
  // ... conteúdo normal da mensagem ...
)}
```

### 7️⃣ **Migration**

Criar migration para adicionar campos:
```python
# backend/apps/chat/migrations/XXXX_add_message_deleted_fields.py

from django.db import migrations, models
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies = [
        ('chat', 'XXXX_previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='message',
            name='deleted_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
```

## ✅ Checklist de Implementação

- [ ] Adicionar campos `is_deleted` e `deleted_at` no modelo Message
- [ ] Criar migration
- [ ] Adicionar handler `handle_message_delete` no webhook
- [ ] Adicionar função `broadcast_message_deleted` em utils/websocket.py
- [ ] Adicionar action `updateMessageDeleted` no chatStore
- [ ] Processar evento `message_deleted` no useChatSocket
- [ ] Atualizar UI para mostrar "Mensagem apagada"
- [ ] Testar com mensagem apagada no WhatsApp
- [ ] Verificar se broadcast funciona em tempo real

## 🧪 Como Testar

1. **Enviar mensagem** via aplicação
2. **Apagar mensagem** no WhatsApp (do próprio celular)
3. **Verificar logs** do backend:
   - `✅ [WEBHOOK DELETE] Mensagem marcada como apagada`
4. **Verificar frontend**:
   - Mensagem deve mostrar "Esta mensagem foi apagada"
   - Deve aparecer em tempo real (sem refresh)

## 📝 Notas

- Evolution API envia `messages.delete` quando mensagem é apagada
- Pode ser apagada pelo remetente ou destinatário
- Mensagem não é removida do banco, apenas marcada como apagada
- Frontend pode escolher ocultar ou mostrar "Mensagem apagada"

