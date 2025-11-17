# 👍 ANÁLISE COMPLETA: Implementação de Reações em Mensagens

**Data:** 22 de outubro de 2025  
**Feature:** Reações (👍 ❤️ 😂 😮 😢 🙏) em mensagens do chat  
**Status:** Análise técnica completa - PRONTO PARA IMPLEMENTAR

---

## 📋 **RESUMO EXECUTIVO:**

✅ **Viável:** Sim, Evolution API suporta nativamente  
✅ **Complexidade:** 🟡 Média (6/10)  
✅ **Tempo:** 4-6 horas  
✅ **Impacto UX:** 🟢 Alto (feature muito solicitada)  
✅ **Dependencies:** Nenhuma (stack atual suporta tudo)

---

## 🎯 **COMO FUNCIONA:**

### **Fluxo de Reação:**

```
1. Usuário clica em mensagem (hover)
   ↓
2. Aparece ReactionPicker (tooltip com emojis)
   ↓
3. Usuário clica em emoji (ex: ❤️)
   ↓
4. Frontend → Backend: POST /messages/{id}/react/
   ↓
5. Backend → Database: Salva reação
   ↓
6. Backend → Evolution API: Envia reação ao WhatsApp
   ↓
7. Backend → WebSocket: Broadcast para todos
   ↓
8. Frontend: Atualiza UI em tempo real
   ↓
9. ✨ Reação aparece abaixo da mensagem!
```

---

## 🔧 **ARQUITETURA TÉCNICA:**

### **1. BACKEND (Django)**

#### **Modelo `MessageReaction`:**

```python
# backend/apps/chat/models.py

class MessageReaction(BaseModel):
    """
    Reações de usuários em mensagens.
    Um usuário pode ter apenas UMA reação por mensagem.
    """
    message = models.ForeignKey(
        'Message',
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    emoji = models.CharField(
        max_length=10,  # Unicode emoji (1-4 chars normalmente)
        help_text="Emoji da reação (ex: ❤️, 👍, 😂)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Um usuário pode ter apenas UMA reação por mensagem
        unique_together = ('message', 'user')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.name} → {self.emoji} na mensagem {self.message.id[:8]}"
```

**Campos:**
- `message` → FK para Message (qual mensagem)
- `user` → FK para User (quem reagiu)
- `emoji` → String com o emoji (ex: "❤️", "👍")
- `created_at` → Quando reagiu

**Regra de negócio:**
- ✅ Usuário pode ter **apenas UMA** reação por mensagem
- ✅ Reagir novamente com mesmo emoji → **REMOVE** reação
- ✅ Reagir com emoji diferente → **SUBSTITUI** reação

---

#### **Serializer `MessageReactionSerializer`:**

```python
# backend/apps/chat/api/serializers.py

class MessageReactionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    
    class Meta:
        model = MessageReaction
        fields = ['id', 'emoji', 'user_id', 'user_name', 'created_at']
        read_only_fields = ['id', 'created_at']

class MessageSerializer(serializers.ModelSerializer):
    # ... campos existentes ...
    
    # 🆕 Adicionar reações agrupadas
    reactions = serializers.SerializerMethodField()
    
    def get_reactions(self, obj):
        """
        Agrupa reações por emoji e conta quantos de cada.
        Exemplo: [
            {"emoji": "❤️", "count": 5, "users": ["Maria", "João", ...]},
            {"emoji": "👍", "count": 2, "users": ["Pedro", "Ana"]}
        ]
        """
        from collections import Counter
        
        reactions_qs = obj.reactions.select_related('user')
        emoji_counter = Counter(r.emoji for r in reactions_qs)
        
        grouped = []
        for emoji, count in emoji_counter.items():
            users = [r.user.name for r in reactions_qs if r.emoji == emoji]
            user_ids = [str(r.user.id) for r in reactions_qs if r.emoji == emoji]
            grouped.append({
                'emoji': emoji,
                'count': count,
                'users': users[:5],  # Primeiros 5 nomes
                'user_ids': user_ids,
                'has_more': len(users) > 5
            })
        
        return grouped
```

**Retorno esperado:**

```json
{
  "id": "...",
  "content": "Olá!",
  "reactions": [
    {
      "emoji": "❤️",
      "count": 5,
      "users": ["Maria", "João", "Pedro", "Ana", "Carlos"],
      "user_ids": ["uuid1", "uuid2", ...],
      "has_more": true
    },
    {
      "emoji": "👍",
      "count": 2,
      "users": ["Laura", "Paulo"],
      "user_ids": ["uuid3", "uuid4"],
      "has_more": false
    }
  ]
}
```

---

#### **Endpoint `POST /messages/{id}/react/`:**

```python
# backend/apps/chat/api/views.py

@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def react_to_message(request, message_id):
    """
    Adiciona ou remove reação de uma mensagem.
    
    POST: Adiciona/altera reação
    DELETE: Remove reação
    
    Body (POST):
        { "emoji": "❤️" }
    """
    try:
        message = Message.objects.get(id=message_id, conversation__tenant=request.user.tenant)
    except Message.DoesNotExist:
        return Response({'error': 'Mensagem não encontrada'}, status=404)
    
    if request.method == 'POST':
        emoji = request.data.get('emoji')
        if not emoji:
            return Response({'error': 'Emoji é obrigatório'}, status=400)
        
        # Criar ou atualizar reação (unique_together garante unicidade)
        reaction, created = MessageReaction.objects.update_or_create(
            message=message,
            user=request.user,
            defaults={'emoji': emoji}
        )
        
        # 📡 Enviar reação ao WhatsApp (via Evolution API)
        send_reaction_to_whatsapp(message, emoji)
        
        # 📡 Broadcast via WebSocket
        broadcast_reaction_update(message)
        
        status_text = 'adicionada' if created else 'atualizada'
        return Response({
            'message': f'Reação {status_text}!',
            'reaction': MessageReactionSerializer(reaction).data
        }, status=201 if created else 200)
    
    elif request.method == 'DELETE':
        # Remover reação
        deleted = MessageReaction.objects.filter(
            message=message,
            user=request.user
        ).delete()[0]
        
        if deleted:
            # 📡 Enviar remoção ao WhatsApp (emoji vazio)
            send_reaction_to_whatsapp(message, '')
            
            # 📡 Broadcast via WebSocket
            broadcast_reaction_update(message)
            
            return Response({'message': 'Reação removida!'}, status=200)
        else:
            return Response({'error': 'Você não reagiu a esta mensagem'}, status=400)
```

---

#### **Integração com Evolution API:**

```python
# backend/apps/chat/utils.py

def send_reaction_to_whatsapp(message: Message, emoji: str):
    """
    Envia reação ao WhatsApp via Evolution API.
    
    Args:
        message: Mensagem a reagir
        emoji: Emoji da reação (ou '' para remover)
    """
    try:
        # Buscar instância ativa
        instance = WhatsAppInstance.objects.filter(
            tenant=message.conversation.tenant,
            is_active=True
        ).first()
        
        if not instance:
            logger.warning(f"⚠️ [REACTION] Nenhuma instância ativa")
            return
        
        # Montar payload
        payload = {
            'key': {
                'remoteJid': message.conversation.contact_phone,
                'id': message.external_id,  # ID da mensagem no WhatsApp
                'fromMe': message.direction == 'outgoing'
            },
            'reaction': emoji  # Emoji ou '' (remove reação)
        }
        
        # Enviar para Evolution API
        import httpx
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{instance.api_url}/message/sendReaction/{instance.instance_name}",
                json=payload,
                headers={'apikey': instance.api_key}
            )
            
            if response.status_code == 200:
                logger.info(f"✅ [REACTION] Reação enviada: {emoji or '(removida)'}")
            else:
                logger.error(f"❌ [REACTION] Erro: {response.status_code} - {response.text}")
    
    except Exception as e:
        logger.error(f"❌ [REACTION] Erro ao enviar: {e}", exc_info=True)


def broadcast_reaction_update(message: Message):
    """
    Broadcast de atualização de reações via WebSocket.
    """
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    from apps.chat.api.serializers import MessageSerializer
    
    channel_layer = get_channel_layer()
    conversation_group = f"chat_tenant_{message.conversation.tenant_id}_conversation_{message.conversation.id}"
    
    # Serializar mensagem com reações atualizadas
    serializer = MessageSerializer(message)
    
    async_to_sync(channel_layer.group_send)(
        conversation_group,
        {
            'type': 'reaction_updated',
            'message': serializer.data
        }
    )
    
    logger.info(f"📡 [REACTION] Broadcast enviado para {conversation_group}")
```

---

### **2. FRONTEND (React + TypeScript)**

#### **Componente `ReactionPicker`:**

```typescript
// frontend/src/modules/chat/components/ReactionPicker.tsx

interface ReactionPickerProps {
  messageId: string;
  onReact: (emoji: string) => void;
  onClose: () => void;
}

export function ReactionPicker({ messageId, onReact, onClose }: ReactionPickerProps) {
  const emojis = ['❤️', '👍', '😂', '😮', '😢', '🙏'];
  
  return (
    <div 
      className="absolute bottom-full mb-2 bg-white rounded-lg shadow-lg p-2 flex gap-2 animate-in fade-in zoom-in duration-200"
      onMouseLeave={onClose}
    >
      {emojis.map(emoji => (
        <button
          key={emoji}
          onClick={() => {
            onReact(emoji);
            onClose();
          }}
          className="text-2xl hover:scale-125 transition-transform active:scale-95"
          title={`Reagir com ${emoji}`}
        >
          {emoji}
        </button>
      ))}
    </div>
  );
}
```

---

#### **Componente `ReactionList`:**

```typescript
// frontend/src/modules/chat/components/ReactionList.tsx

interface Reaction {
  emoji: string;
  count: number;
  users: string[];
  user_ids: string[];
  has_more: boolean;
}

interface ReactionListProps {
  reactions: Reaction[];
  currentUserId: string;
  onReact: (emoji: string) => void;
  onRemove: () => void;
}

export function ReactionList({ reactions, currentUserId, onReact, onRemove }: ReactionListProps) {
  if (!reactions || reactions.length === 0) return null;
  
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {reactions.map(reaction => {
        const hasReacted = reaction.user_ids.includes(currentUserId);
        const tooltip = reaction.has_more
          ? `${reaction.users.slice(0, 3).join(', ')} e mais ${reaction.count - 3}`
          : reaction.users.join(', ');
        
        return (
          <button
            key={reaction.emoji}
            onClick={() => hasReacted ? onRemove() : onReact(reaction.emoji)}
            className={`
              flex items-center gap-1 px-2 py-0.5 rounded-full text-sm
              transition-colors
              ${hasReacted
                ? 'bg-blue-100 border-2 border-blue-500'
                : 'bg-gray-100 border border-gray-300 hover:bg-gray-200'
              }
            `}
            title={tooltip}
          >
            <span>{reaction.emoji}</span>
            <span className="text-xs font-medium text-gray-700">
              {reaction.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
```

---

#### **Integração no `MessageList`:**

```typescript
// frontend/src/modules/chat/components/MessageList.tsx

export function MessageList() {
  const [reactionPickerOpen, setReactionPickerOpen] = useState<string | null>(null);
  const { user } = useAuthStore();
  
  const handleReact = async (messageId: string, emoji: string) => {
    try {
      await api.post(`/chat/messages/${messageId}/react/`, { emoji });
      toast.success('Reação enviada!');
    } catch (error) {
      toast.error('Erro ao reagir');
    }
  };
  
  const handleRemoveReaction = async (messageId: string) => {
    try {
      await api.delete(`/chat/messages/${messageId}/react/`);
      toast.success('Reação removida!');
    } catch (error) {
      toast.error('Erro ao remover reação');
    }
  };
  
  return (
    <div>
      {messages.map(msg => (
        <div
          key={msg.id}
          className="relative group"
          onMouseEnter={() => setReactionPickerOpen(msg.id)}
          onMouseLeave={() => setReactionPickerOpen(null)}
        >
          {/* Mensagem */}
          <div className="...">
            {msg.content}
          </div>
          
          {/* 🆕 Reaction Picker (aparece no hover) */}
          {reactionPickerOpen === msg.id && (
            <ReactionPicker
              messageId={msg.id}
              onReact={(emoji) => handleReact(msg.id, emoji)}
              onClose={() => setReactionPickerOpen(null)}
            />
          )}
          
          {/* 🆕 Lista de reações */}
          <ReactionList
            reactions={msg.reactions || []}
            currentUserId={user.id}
            onReact={(emoji) => handleReact(msg.id, emoji)}
            onRemove={() => handleRemoveReaction(msg.id)}
          />
        </div>
      ))}
    </div>
  );
}
```

---

#### **WebSocket Handler:**

```typescript
// frontend/src/modules/chat/hooks/useChatSocket.ts

useEffect(() => {
  // ... outros handlers ...
  
  const handleReactionUpdate = (data: WebSocketMessage) => {
    if (data.message) {
      console.log('🎉 [WS] Reação atualizada:', data.message);
      // Atualizar mensagem no store
      updateMessage(data.message);
    }
  };
  
  chatWebSocketManager.on('reaction_updated', handleReactionUpdate);
  
  return () => {
    chatWebSocketManager.off('reaction_updated', handleReactionUpdate);
  };
}, []);
```

---

## 📊 **BANCO DE DADOS:**

### **Migration:**

```python
# backend/apps/chat/migrations/00XX_add_reactions.py

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('chat', '00XX_previous_migration'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageReaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('emoji', models.CharField(help_text='Emoji da reação (ex: ❤️, 👍, 😂)', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reactions', to='chat.message')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('message', 'user')},
            },
        ),
    ]
```

---

## 🧪 **PLANO DE TESTES:**

### **Script de Teste (`test_reactions.py`):**

```python
#!/usr/bin/env python
"""
Script de teste para reações em mensagens.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.chat.models import Message, MessageReaction
from apps.auth_custom.models import User

def test_reactions():
    print("🧪 [TEST] Iniciando testes de reações...\n")
    
    # 1. Buscar mensagem e usuários
    message = Message.objects.first()
    user1 = User.objects.first()
    user2 = User.objects.exclude(id=user1.id).first()
    
    print(f"📧 Mensagem: {message.content[:50]}")
    print(f"👤 User 1: {user1.name}")
    print(f"👤 User 2: {user2.name}\n")
    
    # 2. User 1 reage com ❤️
    reaction1, created = MessageReaction.objects.get_or_create(
        message=message,
        user=user1,
        defaults={'emoji': '❤️'}
    )
    print(f"{'✅ Criada' if created else '🔄 Atualizada'}: {user1.name} → ❤️\n")
    
    # 3. User 2 reage com 👍
    reaction2, created = MessageReaction.objects.get_or_create(
        message=message,
        user=user2,
        defaults={'emoji': '👍'}
    )
    print(f"{'✅ Criada' if created else '🔄 Atualizada'}: {user2.name} → 👍\n")
    
    # 4. User 1 muda para 😂
    reaction1.emoji = '😂'
    reaction1.save()
    print(f"🔄 {user1.name} mudou para 😂\n")
    
    # 5. User 1 remove reação
    reaction1.delete()
    print(f"❌ {user1.name} removeu reação\n")
    
    # 6. Listar reações da mensagem
    reactions = message.reactions.all()
    print(f"📊 Reações finais: {reactions.count()}")
    for r in reactions:
        print(f"   {r.emoji} - {r.user.name}")
    
    print("\n✅ [TEST] Testes concluídos!")

if __name__ == '__main__':
    test_reactions()
```

---

## ⏱️ **CRONOGRAMA DE IMPLEMENTAÇÃO:**

### **Fase 1: Backend (2-3h)**
- ✅ Criar modelo `MessageReaction` + migration
- ✅ Criar serializer com agrupamento
- ✅ Criar endpoint `/messages/{id}/react/`
- ✅ Integrar com Evolution API
- ✅ Adicionar broadcast WebSocket
- ✅ Testar com script local

### **Fase 2: Frontend (2-3h)**
- ✅ Criar componente `ReactionPicker`
- ✅ Criar componente `ReactionList`
- ✅ Integrar no `MessageList`
- ✅ Adicionar handler WebSocket
- ✅ Estilizar (animações + hover)
- ✅ Testar responsividade

### **Fase 3: Testes & Deploy (1h)**
- ✅ Testes locais (vários usuários)
- ✅ Testes em Railway (produção)
- ✅ Validar integração WhatsApp
- ✅ Ajustes finais de UX

**TOTAL:** 5-7 horas (1 dia de trabalho)

---

## ✅ **CHECKLIST DE IMPLEMENTAÇÃO:**

### **Backend:**
- [ ] Modelo `MessageReaction` criado
- [ ] Migration aplicada
- [ ] Serializer com agrupamento
- [ ] Endpoint POST/DELETE
- [ ] Integração Evolution API
- [ ] WebSocket broadcast
- [ ] Script de teste local
- [ ] Testes passando

### **Frontend:**
- [ ] Componente `ReactionPicker`
- [ ] Componente `ReactionList`
- [ ] Integração no `MessageList`
- [ ] Handler WebSocket
- [ ] Animações e hover
- [ ] Responsividade mobile
- [ ] Testes manuais

### **Deploy:**
- [ ] Migration rodada em Railway
- [ ] Frontend built e deployed
- [ ] Testes em produção
- [ ] Validação WhatsApp
- [ ] Documentação atualizada

---

## 🎨 **DESIGN REFERENCE (WhatsApp):**

```
┌────────────────────────────────┐
│ Olá, tudo bem?                 │  ← Mensagem
│                                │
│ ❤️ 5   👍 2                    │  ← Reações agrupadas
│ ^      ^                       │
│ │      │                       │
│ │      └─ 2 pessoas reagiram   │
│ └──────── 5 pessoas reagiram   │
└────────────────────────────────┘
```

**Hover na mensagem:**
```
      ❤️ 👍 😂 😮 😢 🙏  ← Reaction Picker
┌────────────────────────────────┐
│ Olá, tudo bem?                 │
└────────────────────────────────┘
```

---

## 🚀 **PRONTO PARA IMPLEMENTAR?**

### **SIM, porque:**
✅ Análise técnica completa  
✅ Evolution API suporta nativamente  
✅ Stack atual tem tudo necessário  
✅ Código bem definido  
✅ Plano de testes pronto  
✅ Cronograma realista (5-7h)

### **Próximo Passo:**

**Me confirma e eu começo a implementar!** 🚀

Ou quer ajustar alguma coisa na análise primeiro?

---

**📌 LEMBRE-SE:** Vamos criar o script de teste PRIMEIRO e validar a lógica localmente antes de fazer commit! [[memory:9724794]]

