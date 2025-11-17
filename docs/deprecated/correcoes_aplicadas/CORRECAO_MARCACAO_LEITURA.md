# 🐛 CORREÇÃO: Marcação Automática de Leitura

**Data:** 29/10/2025  
**Problema:** Mensagens sendo marcadas como lidas (check azul) automaticamente ao chegar, sem usuário visualizar

---

## 📋 Problema Identificado

### Comportamento Incorreto (❌):
1. Usuário envia mensagem do celular (ex: 3112) para aplicação
2. Mensagem chega no WhatsApp
3. ✓ (enviado) → ✓✓ (entregue) → ✓✓ **AZUL (lido)** **automaticamente**
4. Aplicação web está fechada/minimizada
5. Mensagem já aparece como lida sem usuário ter visto

### Causa Raiz:
- No `backend/apps/chat/webhooks.py`, linha **664-670**
- Quando mensagem chegava (`handle_message_upsert`), sistema chamava:
  ```python
  if not from_me:
      send_delivery_receipt(conversation, message)
  ```
- A função `send_delivery_receipt` estava usando endpoint **`/chat/markMessageAsRead`**
- Isso enviava `readMessages` (marcar como LIDA) ao invés de apenas "delivered"

---

## ✅ Correção Implementada

### O que foi feito:
1. **Removida** a chamada automática de `send_delivery_receipt` no webhook
2. Mensagens agora **NÃO são marcadas como lidas automaticamente**
3. Marcação como lida acontece **APENAS** quando:
   - Usuário abre a conversa no frontend
   - Após **2.5 segundos** visualizando
   - Frontend chama `/api/chat/conversations/{id}/mark_as_read/`
   - Backend envia `send_read_receipt` → Evolution API → Check azul

### Código Alterado:
```python
# backend/apps/chat/webhooks.py - linhas 663-669

# 🔔 IMPORTANTE: Se for mensagem recebida (não enviada por nós)
if not from_me:
    # ❌ REMOVIDO: Não marcar como lida automaticamente
    # O read receipt só deve ser enviado quando usuário REALMENTE abrir a conversa
    # Isso é feito via /mark_as_read/ quando frontend abre a conversa (após 2.5s)
    
    # 1. Notificar tenant sobre nova mensagem (toast)
```

---

## 🎯 Comportamento Correto (✅)

### Fluxo Esperado:
1. **Mensagem chega:**
   - ✓✓ Cinza (entregue - automático do WhatsApp)
   - **NÃO marca como lida**

2. **Usuário abre aplicação web:**
   - Vê notificação/badge de mensagens não lidas
   - Clica na conversa

3. **Após 2.5s visualizando:**
   - Frontend: `POST /api/chat/conversations/{id}/mark_as_read/`
   - Backend: `send_read_receipt()` → Evolution API
   - WhatsApp: ✓✓ **Azul** (lido)

---

## 🧪 Como Testar

### Teste 1: Mensagem com App Fechado
1. **Fechar completamente** o navegador/aplicação web
2. **Enviar mensagem** do celular (ex: 3112) para instância
3. **Verificar no celular:** Deve aparecer apenas ✓✓ **CINZA** (entregue)
4. **Aguardar 1 minuto:** Deve continuar ✓✓ **CINZA**
5. ✅ **SUCESSO:** Não marcou como lida

### Teste 2: Mensagem com App Aberto (sem visualizar)
1. **Abrir** aplicação web, mas ficar em outra página (Dashboard)
2. **Enviar mensagem** do celular
3. **Verificar no celular:** ✓✓ **CINZA** (apenas entregue)
4. **Ver notificação** na aplicação (toast/badge)
5. **NÃO clicar** na conversa
6. ✅ **SUCESSO:** Continua ✓✓ **CINZA**

### Teste 3: Mensagem com Visualização Real
1. **Enviar mensagem** do celular
2. **Verificar:** ✓✓ **CINZA**
3. **Abrir aplicação** e **clicar na conversa**
4. **Aguardar 2.5 segundos** visualizando
5. **Verificar no celular:** ✓✓ **AZUL** (lido) ✅
6. ✅ **SUCESSO:** Marcou como lida após visualização real

### Teste 4: Troca Rápida de Conversa
1. **Enviar mensagem** do celular
2. **Abrir conversa** na aplicação
3. **Trocar para outra conversa ANTES de 2.5s**
4. **Verificar no celular:** ✓✓ **CINZA** (não marcou)
5. ✅ **SUCESSO:** Cancelou timeout corretamente

---

## 📊 Impacto

### Benefícios:
✅ Usuário sabe quando mensagem foi **realmente lida**  
✅ Não gera "falsa leitura" quando app está fechado  
✅ Comportamento consistente com WhatsApp Web oficial  
✅ Melhor UX e transparência na comunicação  

### Pontos de Atenção:
⚠️ Aguardar **2-3 minutos** para deploy no Railway  
⚠️ Pode ser necessário **reconectar instância** Evolution após deploy  
⚠️ Testar com **ambas as instâncias** (RBTEC 01 e RBTec 02)  

---

## 🔗 Arquivos Modificados

- `backend/apps/chat/webhooks.py` (linhas 663-669)

## 📝 Commit

```
fix: Remover marcação automática de mensagens como lidas

- Removida chamada automática de send_delivery_receipt no webhook
- Mensagens agora só são marcadas como lidas quando usuário abre conversa
- Comportamento correto: check azul apenas após visualização real (2.5s)
- Evita marcar como lida sem usuário ter visto a mensagem

Closes: Mensagens sendo marcadas como lidas automaticamente
```

---

## ✅ Checklist de Verificação

Após deploy:

- [ ] Deploy concluído (2-3 min)
- [ ] Instância reconectada (se necessário)
- [ ] Teste 1: App fechado → ✓✓ cinza ✅
- [ ] Teste 2: App aberto sem visualizar → ✓✓ cinza ✅
- [ ] Teste 3: Visualização real (2.5s) → ✓✓ azul ✅
- [ ] Teste 4: Troca rápida → ✓✓ cinza ✅

---

**Status:** 🚀 Deploy em andamento (aguardar 2-3 min)



