# 🔧 CORREÇÕES - TEMPO REAL + NOTIFICAÇÕES

## ✅ CORREÇÕES APLICADAS

### **1. Notificações de Grupo** 📱

**Problema reportado:**
```
"qdo a notificação for em grupo, mostre apenas MSG DO GRUPO X"
```

**ANTES:**
```
Notificação: "Olá pessoal, tudo bem?" (mensagem completa)
```

**DEPOIS:**
```
Notificação: "MSG DO GRUPO Grupo do Trabalho"
```

**Código alterado:**
```python
# 📱 Para GRUPOS: mostrar apenas "MSG DO GRUPO X"
if is_group:
    group_name = conversation.group_metadata.get('group_name', 'Grupo WhatsApp') if conversation.group_metadata else 'Grupo WhatsApp'
    notification_text = f"MSG DO GRUPO {group_name}"
else:
    notification_text = content[:100]  # Primeiros 100 caracteres para contatos individuais
```

---

### **2. Debug de Novas Conversas** 🐛

**Problema reportado:**
```
"novas conversas não aparecem na listagem, porem, se estiverem la a conversa do chat atualiza"
```

**Análise:**
- ✅ `conversation_updated` funciona (conversas existentes atualizam)
- ❌ `new_conversation` não está chegando no frontend (novas conversas precisam de F5)

**Logs adicionados:**
```python
logger.info(f"🚀 [WEBSOCKET] Enviando broadcast de NOVA CONVERSA...")
logger.info(f"   Tenant ID: {tenant.id}")
logger.info(f"   Tenant Group: {tenant_group}")
logger.info(f"   Conversation ID: {conversation.id}")
logger.info(f"   Contact: {conversation.contact_name or phone}")
```

**O que vai aparecer nos logs agora:**
```
🚀 [WEBSOCKET] Enviando broadcast de NOVA CONVERSA...
   Tenant ID: a72fbca7-92cd-4aa0-80cb-1c0a02761218
   Tenant Group: chat_tenant_a72fbca7-92cd-4aa0-80cb-1c0a02761218
   Conversation ID: 123e4567-e89b-12d3-a456-426614174000
   Contact: João Silva
✅ [WEBSOCKET] Broadcast de nova conversa enviado com sucesso!
```

---

## 🧪 COMO TESTAR

### **Teste 1: Notificações de Grupo**

1. **Abra Flow Chat** em uma aba
2. **Peça para alguém enviar mensagem em um GRUPO**
3. **Verificar notificação:**
   ```
   ✅ Deve mostrar: "MSG DO GRUPO [Nome do Grupo]"
   ❌ NÃO deve mostrar o conteúdo da mensagem
   ```

### **Teste 2: Novas Conversas em Tempo Real**

1. **Abra Flow Chat** na aba Inbox
2. **Abra console do navegador (F12)**
3. **Peça para alguém NOVO te enviar mensagem** (contato que nunca conversou)
4. **Verificar:**
   
   **A. No console do navegador:**
   ```javascript
   ✅ Deve aparecer: {type: "new_conversation", conversation: {...}}
   ```
   
   **B. Na interface:**
   ```
   ✅ Nova conversa DEVE aparecer automaticamente (SEM dar F5)
   ```
   
   **C. Nos logs Railway:**
   ```
   🚀 [WEBSOCKET] Enviando broadcast de NOVA CONVERSA...
      Tenant ID: ...
      Tenant Group: chat_tenant_...
      Conversation ID: ...
      Contact: ...
   ✅ [WEBSOCKET] Broadcast de nova conversa enviado com sucesso!
   ```

---

## 🐛 SE NÃO FUNCIONAR

### **Problema: Notificação de grupo ainda mostra mensagem completa**

**Verificar:**
1. Deploy terminou? (aguarde ~2-3 minutos após push)
2. Limpar cache do navegador
3. Verificar nos logs Railway:
   ```
   📱 Para GRUPOS: mostrar apenas "MSG DO GRUPO X"
   ```

---

### **Problema: Novas conversas ainda não aparecem**

**Passo 1: Verificar WebSocket conectado**

No console do navegador (F12):
```javascript
// Deve aparecer ao carregar a página:
✅ [TENANT WS] Conectado
```

**Se NÃO aparecer:**
- WebSocket não conectou
- Verificar URL do WebSocket no frontend
- Verificar se backend está aceitando conexões WS

**Passo 2: Verificar logs Railway**

Quando receber mensagem de contato novo:
```
✅ Deve aparecer:
🚀 [WEBSOCKET] Enviando broadcast de NOVA CONVERSA...
✅ [WEBSOCKET] Broadcast de nova conversa enviado com sucesso!

❌ Se NÃO aparecer:
- Broadcast não está sendo enviado
- Verificar se `created=True` está correto
```

**Passo 3: Verificar console do navegador**

Quando receber mensagem:
```javascript
// Console do navegador DEVE mostrar:
{
  type: "new_conversation",
  conversation: {
    id: "...",
    contact_name: "...",
    // ...
  }
}
```

**Se aparecer no console MAS não atualiza a interface:**
- Problema no frontend React
- Verificar se `useEffect` está escutando corretamente
- Verificar se Zustand está atualizando o estado

---

## 📋 CHECKLIST DE TESTE

- [ ] ✅ Deploy Railway terminou
- [ ] ✅ Console do navegador aberto (F12)
- [ ] ✅ Flow Chat aberto na aba Inbox
- [ ] ⏸️ **Teste 1:** Notificação de grupo mostra "MSG DO GRUPO X"
- [ ] ⏸️ **Teste 2:** Nova conversa aparece automaticamente (sem F5)
- [ ] ⏸️ **Teste 3:** Logs Railway mostram broadcast sendo enviado
- [ ] ⏸️ **Teste 4:** Console do navegador mostra evento recebido

---

## 📊 COMMITS

```bash
d3c2d00 - fix: payload 50MB
fec4676 - fix: busca instância (chat)
d9f6a45 - fix: busca instância (campanhas + tasks)
ca51ed5 - fix: notificações grupo + logs debug
```

**Status:** ✅ **Deployando agora** (~2-3 minutos)

---

## 💡 PRÓXIMOS PASSOS

1. ⏸️ **Aguardar deploy** (~2-3 minutos)
2. ⏸️ **Testar notificações de grupo**
3. ⏸️ **Testar novas conversas**
4. ⏸️ **Me enviar:**
   - Logs do Railway (se novas conversas não aparecerem)
   - Console do navegador (F12) screenshot
   - Comportamento observado

---

**🚀 Vamos descobrir o que está acontecendo com as novas conversas!**

Se os logs mostrarem que o broadcast está sendo enviado mas não chega no frontend, o problema é no WebSocket ou no frontend React. Se os logs NÃO mostrarem o broadcast, o problema é no backend.

