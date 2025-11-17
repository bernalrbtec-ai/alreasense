# 🔍 ANÁLISE: Por que novas conversas não aparecem em tempo real?

**Data:** 22 de outubro de 2025  
**Problema:** Usuário relata que "novas conversas não aparecem na listagem, porém, se estiverem lá a conversa do chat atualiza"

---

## 📊 **FLUXO COMPLETO (COMO DEVERIA FUNCIONAR)**

### **1. Webhook Recebe Mensagem:**
```python
# backend/apps/chat/webhooks.py - linha 214-222

conversation, created = Conversation.objects.get_or_create(
    tenant=tenant,
    contact_phone=phone,
    defaults=defaults
)

if created:
    # 📡 Broadcast nova conversa
    # Linha 505-511
```

### **2. Backend Envia WebSocket:**
```python
# backend/apps/chat/webhooks.py - linha 505-511

async_to_sync(channel_layer.group_send)(
    f"chat_tenant_{tenant.id}",
    {
        'type': 'new_conversation',
        'conversation': conv_data_serializable
    }
)
```

✅ **LOGS CONFIRMAM:** Backend está enviando! (linhas 499-513)

---

### **3. Frontend Recebe WebSocket:**
```typescript
// frontend/src/modules/chat/hooks/useTenantSocket.ts - linha 42-83

case 'new_conversation':
    console.log('🆕 [TENANT WS] Nova conversa:', data.conversation);
    if (data.conversation) {
        addConversation(data.conversation);  // ← ADICIONA AO ZUSTAND
        // Toast notifications...
    }
    break;
```

✅ **HOOK REGISTRADO:** Layout.tsx (linha 77) chama `useTenantSocket()`

---

### **4. Zustand Store Adiciona:**
```typescript
// frontend/src/modules/chat/store/chatStore.ts - linha 62-72

addConversation: (conversation) => set((state) => {
    // Evitar duplicatas
    const exists = state.conversations.some(c => c.id === conversation.id);
    if (exists) {
        return state; // ← NÃO ADICIONA SE JÁ EXISTE!
    }
    // Adicionar no início da lista
    return {
        conversations: [conversation, ...state.conversations]
    };
}),
```

✅ **LÓGICA OK:** Adiciona no início, evita duplicatas

---

## 🐛 **PROBLEMA IDENTIFICADO!**

### **ConversationList.tsx - Linha 34-61:**

```typescript
useEffect(() => {
    if (!activeDepartment) return;

    const fetchConversations = async () => {
        const params: any = {
            ordering: '-last_message_at'
        };

        // ⚠️ AQUI ESTÁ O PROBLEMA!
        if (activeDepartment.id === 'inbox') {
            params.status = 'pending';
        } else {
            params.department = activeDepartment.id;
        }

        const response = await api.get('/chat/conversations/', { params });
        const convs = response.data.results || response.data;
        setConversations(convs);  // ← SOBRESCREVE O ESTADO!
    };

    fetchConversations();
}, [activeDepartment, setConversations]);
```

---

## 🔥 **ROOT CAUSE:**

### **Cenário 1: Usuário está no Inbox**
1. ✅ Nova conversa chega via WebSocket
2. ✅ `addConversation()` adiciona ao estado Zustand
3. ✅ Conversa aparece na lista (status = 'pending')

### **Cenário 2: Usuário está em outro departamento**
1. ✅ Nova conversa chega via WebSocket (status = 'pending')
2. ✅ `addConversation()` adiciona ao estado Zustand
3. ❌ **MAS:** ConversationList filtra por `activeDepartment`
4. ❌ **RESULTADO:** Conversa é adicionada ao array, mas não aparece na lista filtrada!

### **Cenário 3: Usuário troca de departamento**
1. ❌ `fetchConversations()` é chamado
2. ❌ **SOBRESCREVE** o estado com apenas conversas do backend
3. ❌ **PERDE** conversas adicionadas via WebSocket que ainda não foram salvas

---

## 🎯 **EVIDÊNCIAS:**

### **Usuário disse:**
> "novas conversas não aparecem na listagem, porém, se estiverem lá a conversa do chat atualiza"

**Tradução:**
- ❌ "não aparecem na listagem" = ConversationList não mostra (filtro/refetch)
- ✅ "conversa do chat atualiza" = WebSocket de mensagens funciona (ChatConsumer)

---

## 🔍 **POSSÍVEIS CAUSAS:**

| # | Causa | Probabilidade | Explicação |
|---|-------|---------------|------------|
| **1** | **Filtro de departamento** | 🔴 **ALTA** | Nova conversa tem `status='pending'` e `department=null`, então só aparece no Inbox |
| **2** | **Race condition** | 🟡 MÉDIA | WebSocket adiciona → useEffect refetch → sobrescreve estado |
| **3** | **Duplicação** | 🟢 BAIXA | `addConversation` detecta duplicata e não adiciona |
| **4** | **WebSocket não conectado** | 🟢 BAIXA | Logs confirmam que está conectado |

---

## 💡 **SOLUÇÕES PROPOSTAS:**

### **OPÇÃO 1: Filtrar no frontend (Simples) ⭐ RECOMENDADO**

**Vantagem:** Não perde conversas ao trocar departamento  
**Desvantagem:** Array cresce (mas ok para <1000 conversas)

```typescript
// ConversationList.tsx

// ❌ ANTES: Buscar do backend sempre
useEffect(() => {
    fetchConversations(); // Sobrescreve estado
}, [activeDepartment]);

// ✅ DEPOIS: Buscar apenas na montagem, filtrar localmente
useEffect(() => {
    fetchConversations(); // Uma vez só
}, []); // Sem dependência de activeDepartment!

// Filtrar no render
const filteredConversations = conversations.filter((conv) => {
    // Filtro de busca
    const matchesSearch = conv.contact_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          conv.contact_phone.includes(searchTerm);
    
    // Filtro de departamento
    if (activeDepartment?.id === 'inbox') {
        return matchesSearch && conv.status === 'pending';
    } else if (activeDepartment?.id) {
        return matchesSearch && conv.department?.id === activeDepartment.id;
    }
    
    return matchesSearch;
});
```

---

### **OPÇÃO 2: Merge inteligente (Complexo)**

**Vantagem:** Mantém sincronização com backend  
**Desvantagem:** Mais complexo, pode ter race conditions

```typescript
const fetchConversations = async () => {
    const response = await api.get('/chat/conversations/', { params });
    const newConvs = response.data.results || response.data;
    
    // Merge com conversas existentes do WebSocket
    setConversations(prevConvs => {
        const merged = [...prevConvs];
        newConvs.forEach(newConv => {
            const existingIndex = merged.findIndex(c => c.id === newConv.id);
            if (existingIndex >= 0) {
                merged[existingIndex] = newConv; // Atualizar
            } else {
                merged.push(newConv); // Adicionar
            }
        });
        return merged;
    });
};
```

---

### **OPÇÃO 3: Invalidar cache + refetch (Backend-heavy)**

**Vantagem:** Backend é fonte da verdade  
**Desvantagem:** Muitas requests, pode ser lento

```typescript
// Após receber new_conversation via WebSocket
case 'new_conversation':
    addConversation(data.conversation);
    
    // ✨ NOVO: Invalidar cache
    setTimeout(() => {
        fetchConversations(); // Refetch do backend
    }, 500);
    break;
```

---

## 🚀 **RECOMENDAÇÃO FINAL:**

### **IMPLEMENTAR OPÇÃO 1:**

1. ✅ **Simples de implementar** (5 minutos)
2. ✅ **Não quebra funcionalidades existentes**
3. ✅ **Reduz requests ao backend**
4. ✅ **Mantém WebSocket como fonte de novas conversas**
5. ✅ **Filtro local é instantâneo**

### **Mudanças necessárias:**

```typescript
// ConversationList.tsx

// 1. Buscar conversas apenas UMA VEZ ao carregar
useEffect(() => {
    const fetchConversations = async () => {
        try {
            setLoading(true);
            const response = await api.get('/chat/conversations/', {
                params: { ordering: '-last_message_at' }
            });
            const convs = response.data.results || response.data;
            setConversations(convs);
        } catch (error) {
            console.error('❌ Erro ao carregar conversas:', error);
        } finally {
            setLoading(false);
        }
    };

    // Buscar apenas ao montar o componente
    if (conversations.length === 0) {
        fetchConversations();
    }
}, []); // ← SEM activeDepartment!

// 2. Filtrar localmente baseado em activeDepartment
const filteredConversations = conversations.filter((conv) => {
    // Filtro de busca
    const matchesSearch = 
        conv.contact_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        conv.contact_phone.includes(searchTerm);
    
    if (!matchesSearch) return false;
    
    // Filtro de departamento
    if (activeDepartment?.id === 'inbox') {
        return conv.status === 'pending' && !conv.department;
    } else if (activeDepartment?.id) {
        return conv.department?.id === activeDepartment.id;
    }
    
    return false;
});
```

---

## ✅ **BENEFÍCIOS:**

1. ✅ Novas conversas aparecem **IMEDIATAMENTE** via WebSocket
2. ✅ Não perde conversas ao trocar departamento
3. ✅ Menos requests ao backend
4. ✅ Filtro local é mais rápido
5. ✅ Código mais simples e previsível

---

## 📝 **NOTAS ADICIONAIS:**

### **Quando refetch é necessário:**

- ✅ Após fechar/reabrir conversa
- ✅ Após transferir conversa
- ✅ Após criar nova conversa manualmente
- ✅ Ao fazer login (inicial)

### **Quando NÃO precisa refetch:**

- ❌ Ao trocar departamento (filtro local!)
- ❌ Ao receber nova mensagem (WebSocket!)
- ❌ Ao receber nova conversa (WebSocket!)

---

## 🎯 **PRÓXIMOS PASSOS:**

1. ✅ Analisar código (concluído)
2. 🔜 **Implementar OPÇÃO 1**
3. 🔜 Testar em Railway
4. 🔜 Validar com usuário

---

**✅ Análise completa!** Problema identificado e solução pronta para implementar.

