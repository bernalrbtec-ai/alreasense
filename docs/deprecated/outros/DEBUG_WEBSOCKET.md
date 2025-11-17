# 🔍 DEBUG - WebSocket e Tempo Real

## ✅ O QUE JÁ ESTÁ CORRETO NO CÓDIGO

1. ✅ WebSocket do tenant ativo no `Layout.tsx`
2. ✅ Handler para `new_conversation` implementado
3. ✅ Chama `addConversation()` corretamente
4. ✅ Backend faz broadcast via `channel_layer.group_send`

---

## 🧪 COMO TESTAR SE ESTÁ FUNCIONANDO

### **1. Abrir Console do Navegador (F12)**

Procure por estas mensagens:

```
✅ Mensagens esperadas quando funciona:
🔌 [TENANT WS] Conectando ao grupo do tenant: <uuid>
✅ [TENANT WS] Conectado ao grupo do tenant!
   🔔 NOTIFICAÇÕES TOAST ATIVAS - Aguardando mensagens...

🆕 Quando nova conversa chegar:
📨 [TENANT WS] Mensagem recebida: {type: "new_conversation", ...}
🆕 [TENANT WS] Nova conversa: {contact_name: "...", ...}
```

```
❌ Mensagens de ERRO (se tiver problema):
❌ [TENANT WS] Erro: ...
🔌 [TENANT WS] Conexão fechada: 1006
🔄 [TENANT WS] Reconectando em ...ms
```

---

### **2. Teste Prático**

**Enquanto está com o Flow Chat aberto:**

1. Abra WhatsApp no celular
2. Envie mensagem de um contato novo (que não tem conversa ainda)
3. **OBSERVE** o console do navegador

**✅ Se funcionar:**
- Console mostra: `🆕 [TENANT WS] Nova conversa`
- Conversa aparece na lista **INSTANTANEAMENTE**
- Não precisa dar refresh

**❌ Se NÃO funcionar:**
- Console NÃO mostra nada
- Conversa só aparece depois de refresh (F5)
- Ou mostra erro de WebSocket

---

## 🔧 SOLUÇÕES SE NÃO FUNCIONAR

### **Problema 1: WebSocket não conecta**
```
Sintoma: Console mostra "Erro" ou "Conexão fechada"
Causa: Backend não está rodando ou URL errada

Solução:
1. Verificar se Railway fez deploy
2. Verificar variável VITE_WS_URL no frontend
```

### **Problema 2: WebSocket conecta mas não recebe mensagens**
```
Sintoma: Console mostra "✅ Conectado" mas não mostra "Nova conversa"
Causa: Backend não está fazendo broadcast OU tenant_id errado

Solução:
1. Verificar logs do Railway (backend)
2. Procurar por "📡 [WEBSOCKET] Nova conversa broadcast"
3. Se não aparecer, problema no webhook backend
```

### **Problema 3: Recebe mensagem mas não atualiza lista**
```
Sintoma: Console mostra "Nova conversa" mas lista não muda
Causa: Problema no Zustand store

Solução:
1. Verificar se addConversation está funcionando
2. Console: useChatStore.getState().conversations
```

---

## 🎯 CHECKLIST APÓS DEPLOY

- [ ] Abrir console do navegador (F12)
- [ ] Verificar mensagem: `✅ [TENANT WS] Conectado`
- [ ] Enviar mensagem de contato novo
- [ ] Ver no console: `🆕 [TENANT WS] Nova conversa`
- [ ] Conversa aparece na lista instantaneamente
- [ ] **Se não funcionar:** Copiar logs do console e enviar

---

## 📋 COMANDOS ÚTEIS NO CONSOLE

```javascript
// Ver conversas na store
useChatStore.getState().conversations

// Ver se WebSocket está conectado
// (Procurar por "✅ [TENANT WS] Conectado" nos logs)

// Ver tenant_id do usuário
useAuthStore.getState().user.tenant_id

// Forçar reload das conversas
window.location.reload()
```

---

## ⏱️ TIMING ESPERADO

**Com código corrigido:**
- Nova mensagem chega no WhatsApp
- **< 1 segundo:** Backend recebe webhook
- **< 1 segundo:** Backend faz broadcast WebSocket
- **< 1 segundo:** Frontend recebe e atualiza lista
- **TOTAL:** ~1-2 segundos (tempo real!)

**Com código antigo (bug):**
- Nova mensagem chega
- Backend processa
- Frontend NÃO recebe
- **Precisa dar refresh manual (F5)**

---

**🎯 Aguarde o deploy terminar e teste! Se não funcionar, copie os logs do console.**

