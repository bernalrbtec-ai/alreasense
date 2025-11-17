# 🔧 Correções: Departamento Padrão e Mensagens

## 📋 Problemas Identificados

1. **Conversas aparecem no Inbox mesmo tendo `default_department` configurado**
2. **Mensagens não aparecem até enviar uma mensagem**
3. **Modal de transferência mostra "N/A" para departamento atual**

## ✅ Correções Implementadas

### 1. **Backend - `connections/webhook_views.py`**
- ✅ **Problema:** `handle_message_upsert` não estava passando `wa_instance` e `connection` para `chat_handle_message`
- ✅ **Correção:** Agora busca `wa_instance` com `select_related('default_department')` e passa para `chat_handle_message`
- ✅ **Resultado:** `default_department` será aplicado quando `messages.upsert` chegar

### 2. **Backend - `chat/webhooks.py`**
- ✅ **Problema:** Logs detalhados adicionados para identificar onde o departamento se perde
- ✅ **Correção:** Verificação dupla se `default_department` foi aplicado após `get_or_create`
- ✅ **Resultado:** Logs mostram estado ANTES e DEPOIS do processamento

### 3. **Backend - `chat/api/serializers.py`**
- ✅ **Problema:** `department_name` retornava `None` quando `department` era `null`
- ✅ **Correção:** Mudado para `SerializerMethodField` que retorna string vazia quando não há departamento
- ✅ **Resultado:** Frontend recebe string vazia ao invés de `None`

### 4. **Frontend - `TransferModal.tsx`**
- ✅ **Problema:** Modal tentava acessar `conversation.department_data?.name` que não existe
- ✅ **Correção:** Agora usa `conversation.department_name` ou fallbacks
- ✅ **Resultado:** Modal mostra nome do departamento corretamente

## 🔍 Problema Principal Identificado

**Os eventos `messages.upsert` NÃO estão chegando no backend!**

Pelos logs, apenas `messages.update` (status de mensagens enviadas) está chegando, não `messages.upsert` (mensagens recebidas).

### Por que isso acontece?
1. O webhook global da Evolution API pode não estar configurado para enviar `messages.upsert`
2. Ou o webhook está configurado para outro endpoint que não processa corretamente
3. Ou os eventos `messages.upsert` estão sendo enviados mas não estão sendo processados

### Como verificar?
1. Verificar se o webhook global está configurado na Evolution API
2. Verificar se o evento `messages.upsert` está na lista de eventos habilitados
3. Verificar os logs do backend quando uma mensagem é recebida

## 📝 Próximos Passos

1. **Verificar configuração do webhook global na Evolution API:**
   - URL deve ser: `https://alreasense-backend-production.up.railway.app/webhooks/evolution/`
   - Eventos habilitados devem incluir: `messages.upsert`, `messages.update`, etc.

2. **Testar recebimento de mensagem:**
   - Enviar uma mensagem para o número configurado
   - Verificar logs do backend para ver se `messages.upsert` chega
   - Verificar se o `default_department` é aplicado

3. **Se `messages.upsert` não chegar:**
   - Configurar webhook global na Evolution API manualmente
   - Ou verificar se há outro endpoint que precisa ser configurado

## 🎯 Status das Correções

- ✅ Backend: `default_department` sendo passado corretamente
- ✅ Backend: Logs detalhados adicionados
- ✅ Backend: `department_name` retornando string vazia quando null
- ✅ Frontend: Modal de transferência corrigido
- ⚠️ **Pendente:** Verificar se webhook global está configurado para enviar `messages.upsert`

