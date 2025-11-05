# 🚀 OTIMIZAÇÕES DE PERFORMANCE - CHAT

## 📊 PROBLEMAS IDENTIFICADOS

### 1. **N+1 Queries - unread_count** ⚠️ CRÍTICO
**Problema:** `unread_count` é calculado em tempo real para cada conversa na lista
**Impacto:** Se há 100 conversas, faz 100 queries extras
**Código:** `backend/apps/chat/models.py:160-166`

```python
@property
def unread_count(self):
    """Conta mensagens não lidas (incoming que não estão 'seen')."""
    return self.messages.filter(
        direction='incoming',
        status__in=['sent', 'delivered']
    ).count()
```

**Solução:** Calcular em batch usando `annotate()` ou campo denormalizado

---

### 2. **N+1 Queries - get_last_message** ⚠️ CRÍTICO
**Problema:** `get_last_message()` faz query para cada conversa na lista
**Impacto:** Se há 100 conversas, faz 100 queries extras
**Código:** `backend/apps/chat/api/serializers.py:208-213`

```python
def get_last_message(self, obj):
    """Retorna a última mensagem da conversa."""
    last_message = obj.messages.order_by('-created_at').first()
    if last_message:
        return MessageSerializer(last_message).data
    return None
```

**Solução:** Usar `prefetch_related()` com `Prefetch()` para buscar última mensagem

---

### 3. **N+1 Queries - get_instance_friendly_name** ⚠️ MÉDIO
**Problema:** Faz query para cada conversa para buscar nome amigável da instância
**Impacto:** Se há 100 conversas, faz 100 queries extras
**Código:** `backend/apps/chat/api/serializers.py:215-230`

**Solução:** Usar `select_related()` ou cache

---

### 4. **N+1 Queries - get_contact_tags** ⚠️ MÉDIO
**Problema:** Faz query para cada conversa para buscar tags do contato
**Impacto:** Se há 100 conversas, faz 100 queries extras
**Código:** `backend/apps/chat/api/serializers.py:232-249`

**Solução:** Usar `prefetch_related()` ou cache

---

### 5. **Mensagens não paginadas** ⚠️ CRÍTICO
**Problema:** Carrega TODAS as mensagens de uma vez
**Impacto:** Se conversa tem 1000 mensagens, carrega todas de uma vez
**Código:** `backend/apps/chat/api/views.py:874-886`

**Solução:** Implementar paginação (limit/offset ou cursor)

---

### 6. **Conversas sem paginação** ⚠️ MÉDIO
**Problema:** Carrega TODAS as conversas de uma vez
**Impacto:** Se há 1000 conversas, carrega todas de uma vez
**Código:** `frontend/src/modules/chat/components/ConversationList.tsx:61`

**Solução:** Implementar paginação infinita (scroll)

---

### 7. **Verificações S3 no serializer** ⚠️ BAIXO
**Problema:** Verifica existência de arquivo no S3 para cada attachment
**Impacto:** Lentidão ao serializar mensagens com muitos attachments
**Código:** `backend/apps/chat/api/serializers.py:48-111`

**Solução:** Cache melhor ou remover verificação (assumir que existe)

---

### 8. **Componentes não memoizados** ⚠️ MÉDIO
**Problema:** Componentes re-renderizam mesmo sem mudanças
**Impacto:** Re-renders desnecessários causam lag
**Código:** `frontend/src/modules/chat/components/`

**Solução:** Usar `React.memo()` e `useMemo()`/`useCallback()`

---

### 9. **Fade-in sequencial** ⚠️ BAIXO
**Problema:** Delay de 50ms entre cada mensagem para efeito fade-in
**Impacto:** Se há 100 mensagens, demora 5 segundos para todas aparecerem
**Código:** `frontend/src/modules/chat/components/MessageList.tsx:139-143`

**Solução:** Reduzir delay ou fazer fade-in em batch

---

## ✅ SOLUÇÕES PROPOSTAS

### **Prioridade ALTA (Crítico):**

1. **Otimizar unread_count** - Calcular em batch
2. **Otimizar get_last_message** - Usar prefetch_related
3. **Adicionar paginação para mensagens** - Limitar e paginar

### **Prioridade MÉDIA:**

4. **Otimizar get_instance_friendly_name** - Cache ou select_related
5. **Otimizar get_contact_tags** - Cache ou prefetch_related
6. **Memoizar componentes React** - React.memo, useMemo, useCallback
7. **Adicionar paginação para conversas** - Infinite scroll

### **Prioridade BAIXA:**

8. **Otimizar verificações S3** - Melhorar cache
9. **Otimizar fade-in** - Reduzir delay ou batch

---

## 📝 IMPLEMENTAÇÃO

### **1. Otimizar unread_count (CRÍTICO)**

**Opção A: Campo denormalizado (Recomendado)**
- Adicionar campo `unread_count` na tabela `chat_conversation`
- Atualizar via signals quando mensagem é criada/atualizada
- Vantagem: Mais rápido, sem queries extras
- Desvantagem: Precisa manter sincronizado

**Opção B: Calcular em batch (Mais simples)**
- Usar `annotate()` no queryset para calcular unread_count
- Vantagem: Não precisa mudar schema
- Desvantagem: Ainda faz join, mas apenas 1 query

**Recomendação:** Opção B primeiro (mais simples), depois migrar para A se necessário

---

### **2. Otimizar get_last_message (CRÍTICO)**

**Solução:** Usar `prefetch_related()` com `Prefetch()` para buscar última mensagem

```python
from django.db.models import Prefetch

queryset = Conversation.objects.select_related(
    'tenant', 'department', 'assigned_to'
).prefetch_related(
    'participants',
    Prefetch(
        'messages',
        queryset=Message.objects.order_by('-created_at')[:1],
        to_attr='last_message_list'
    )
)
```

No serializer:
```python
def get_last_message(self, obj):
    """Retorna a última mensagem da conversa."""
    if hasattr(obj, 'last_message_list') and obj.last_message_list:
        return MessageSerializer(obj.last_message_list[0]).data
    return None
```

---

### **3. Adicionar paginação para mensagens (CRÍTICO)**

**Solução:** Implementar paginação com limit/offset

```python
@action(detail=True, methods=['get'])
def messages(self, request, pk=None):
    """Lista mensagens de uma conversa específica (paginado)."""
    conversation = self.get_object()
    
    # Paginação
    limit = int(request.query_params.get('limit', 50))  # Default 50
    offset = int(request.query_params.get('offset', 0))
    
    messages = Message.objects.filter(
        conversation=conversation
    ).select_related('sender').prefetch_related('attachments').order_by('-created_at')[offset:offset+limit]
    
    # Reverter ordem para exibir (mais antigas primeiro)
    messages = list(messages)
    messages.reverse()
    
    serializer = MessageSerializer(messages, many=True)
    return Response({
        'results': serializer.data,
        'count': Message.objects.filter(conversation=conversation).count(),
        'limit': limit,
        'offset': offset,
        'has_more': offset + limit < Message.objects.filter(conversation=conversation).count()
    })
```

---

### **4. Otimizar get_instance_friendly_name (MÉDIO)**

**Solução:** Cache ou select_related

```python
def get_instance_friendly_name(self, obj):
    """Retorna nome amigável da instância."""
    if not obj.instance_name:
        return None
    
    # Cache (5 minutos)
    cache_key = f"instance_friendly_name:{obj.instance_name}"
    friendly_name = cache.get(cache_key)
    
    if friendly_name is None:
        from apps.notifications.models import WhatsAppInstance
        instance = WhatsAppInstance.objects.filter(
            instance_name=obj.instance_name,
            is_active=True
        ).values('friendly_name').first()
        
        friendly_name = instance['friendly_name'] if instance else obj.instance_name
        cache.set(cache_key, friendly_name, 300)  # 5 min
    
    return friendly_name
```

---

### **5. Otimizar get_contact_tags (MÉDIO)**

**Solução:** Cache ou prefetch_related

```python
def get_contact_tags(self, obj):
    """Busca as tags do contato pelo telefone."""
    # Cache (10 minutos)
    cache_key = f"contact_tags:{obj.tenant_id}:{obj.contact_phone}"
    tags = cache.get(cache_key)
    
    if tags is None:
        try:
            contact = Contact.objects.prefetch_related('tags').get(
                tenant=obj.tenant,
                phone=obj.contact_phone,
                is_active=True
            )
            tags = [
                {'id': str(tag.id), 'name': tag.name, 'color': tag.color}
                for tag in contact.tags.all()
            ]
        except Contact.DoesNotExist:
            tags = []
        
        cache.set(cache_key, tags, 600)  # 10 min
    
    return tags
```

---

### **6. Memoizar componentes React (MÉDIO)**

**Solução:** Usar `React.memo()` para componentes que não precisam re-renderizar

```typescript
// MessageList.tsx
export const MessageList = React.memo(() => {
  // ... código
}, (prevProps, nextProps) => {
  // Comparação customizada se necessário
});

// ConversationList.tsx
export const ConversationItem = React.memo(({ conversation }) => {
  // ... código
});
```

---

### **7. Adicionar paginação para conversas (MÉDIO)**

**Solução:** Infinite scroll

```typescript
// Frontend: ConversationList.tsx
const [hasMore, setHasMore] = useState(true);
const [offset, setOffset] = useState(0);

const loadMore = async () => {
  if (!hasMore || loading) return;
  
  const response = await api.get('/chat/conversations/', {
    params: { 
      ordering: '-last_message_at',
      limit: 50,
      offset: offset + 50
    }
  });
  
  if (response.data.results.length === 0) {
    setHasMore(false);
  } else {
    setConversations([...conversations, ...response.data.results]);
    setOffset(offset + 50);
  }
};
```

---

## 🎯 PRIORIZAÇÃO

### **Fase 1 (Crítico - Implementar primeiro):**
1. ✅ Otimizar unread_count (batch)
2. ✅ Otimizar get_last_message (prefetch_related)
3. ✅ Adicionar paginação para mensagens

### **Fase 2 (Médio - Implementar depois):**
4. ✅ Otimizar get_instance_friendly_name (cache)
5. ✅ Otimizar get_contact_tags (cache)
6. ✅ Memoizar componentes React
7. ✅ Adicionar paginação para conversas

### **Fase 3 (Baixo - Nice to have):**
8. ✅ Otimizar verificações S3
9. ✅ Otimizar fade-in

---

## 📈 IMPACTO ESPERADO

### **Antes:**
- 100 conversas: ~300 queries (3 por conversa)
- 1000 mensagens: Carrega todas de uma vez
- Tempo de resposta: ~2-5 segundos

### **Depois:**
- 100 conversas: ~5 queries (1 principal + 4 auxiliares)
- 1000 mensagens: Carrega 50 por vez (paginação)
- Tempo de resposta: ~200-500ms

**Melhoria esperada:** 10-25x mais rápido

---

## 🔧 IMPLEMENTAÇÃO

Posso implementar as otimizações da Fase 1 (Crítico) agora. Devo continuar?

