# 📋 FLUXO COMPLETO DE NOTIFICAÇÕES DE TAREFAS

## ⏰ QUANDO RODA

O scheduler verifica tarefas **a cada 60 segundos** em loop contínuo.

---

## 🔄 CICLO DE VERIFICAÇÃO

O scheduler verifica **duas janelas** a cada ciclo:

### 1️⃣ JANELA DE LEMBRETE (15 minutos antes)
- **Quando:** Entre 10-20 minutos antes do `due_date`
- **Filtro:** `notification_sent=False` (só notifica se ainda não foi notificado)
- **O que faz:**
  - Notifica `assigned_to` (se houver)
  - Notifica `created_by` (se diferente de `assigned_to`)
  - Notifica contatos relacionados (se `metadata.notify_contacts=True`)
  - Marca `notification_sent=True` se pelo menos uma notificação foi enviada

### 2️⃣ JANELA DE MOMENTO EXATO
- **Quando:** Entre 5 minutos antes e 1 minuto depois do `due_date`
- **Filtro:** `notification_sent=False` (só notifica se NÃO foi notificado no lembrete)
- **O que faz:**
  - Notifica `assigned_to` (se houver)
  - Notifica `created_by` (se diferente de `assigned_to`)
  - Notifica contatos relacionados (se `metadata.notify_contacts=True`)
  - **NÃO marca `notification_sent=True`** (permite notificar novamente se necessário)

---

## 📤 TIPOS DE NOTIFICAÇÃO POR USUÁRIO/CONTATO

### Para cada usuário (`assigned_to` ou `created_by`):

1. **WebSocket (navegador)** - Sempre enviado
   - Tipo: `task_notification`
   - Grupo: `tenant_{tenant_id}`
   - Conteúdo: Mensagem com título e data/hora

2. **WhatsApp** - Se `user.notify_whatsapp=True` e `user.phone` preenchido
   - URL: `{base_url}/message/sendText/{instance_name}`
   - Retry: 2 tentativas
   - Conteúdo: Mensagem formatada com detalhes da tarefa

### Para cada contato relacionado:

1. **WhatsApp** - Se `metadata.notify_contacts=True`
   - URL: `{base_url}/message/sendText/{instance_name}`
   - Retry: 2 tentativas por contato
   - Conteúdo: Mensagem personalizada com nome do contato

---

## 🔍 ANÁLISE DO PROBLEMA: 4 NOTIFICAÇÕES

### Cenário possível:

**Tarefa:**
- `assigned_to` = Usuário A (você)
- `created_by` = Usuário A (você) - **MESMO USUÁRIO**
- `related_contacts` = 2 contatos
- `metadata.notify_contacts` = True

**O que acontece:**

#### No LEMBRETE (15min antes):
1. ✅ Notifica `assigned_to` (você) → **1 notificação**
   - WebSocket: 1x
   - WhatsApp: 1x (se habilitado)
2. ❌ NÃO notifica `created_by` (mesmo usuário, pulado)
3. ✅ Notifica contatos relacionados → **2 notificações** (1 por contato)
   - WhatsApp: 2x

**Total no lembrete: 1 (você) + 2 (contatos) = 3 notificações**

#### No MOMENTO EXATO:
- **PROBLEMA:** Se `notification_sent=False` ainda (por algum motivo), notifica novamente
- Ou se a tarefa entrou nas duas janelas simultaneamente

**Total no momento exato: +1 notificação**

**TOTAL: 4 notificações**

---

## 🐛 POSSÍVEIS CAUSAS DA DUPLICAÇÃO

### 1. **Race Condition no `notification_sent`**
- Tarefa encontrada em ambas as janelas antes de salvar `notification_sent=True`
- Solução: Usar `select_for_update()` para lock

### 2. **Múltiplas Instâncias do Scheduler**
- Várias threads rodando simultaneamente
- Solução: Já implementada com flags `_scheduler_started`

### 3. **Tarefa Entra em Ambas as Janelas**
- Se `due_date` está exatamente na borda das janelas
- Exemplo: Tarefa às 11:30, verificação às 11:15 → entra no lembrete
- Verificação às 11:30 → entra no momento exato
- Solução: Melhorar lógica de janelas

### 4. **Retry do WhatsApp Contando como Nova Notificação**
- Se WhatsApp falha e retry, pode estar contando como nova
- Solução: Verificar se retry está duplicando

---

---

## 📊 EXEMPLO PRÁTICO: TAREFA ÀS 11:30

### Cenário:
- **Tarefa:** "Reunião com cliente"
- **Due Date:** 11:30:00
- **Assigned To:** Você (paulo.bernal@rbtec.com.br)
- **Created By:** Você (mesmo usuário)
- **Contatos Relacionados:** 2 contatos
- **Notify Contacts:** True

### Timeline:

#### 11:15:00 - Verificação do Scheduler
- **Janela Lembrete:** 11:15:00 - 11:25:00 ✅ (tarefa às 11:30 está na janela)
- **Encontra tarefa:** `notification_sent=False`
- **Ações:**
  1. Notifica `assigned_to` (você) → **1 notificação**
     - WebSocket: 1x
     - WhatsApp: 1x (se habilitado)
  2. Pula `created_by` (mesmo usuário)
  3. Notifica 2 contatos → **2 notificações**
     - WhatsApp: 2x
- **Marca:** `notification_sent=True`
- **Total enviado:** 3 notificações (1 para você + 2 para contatos)

#### 11:16:00 - Verificação do Scheduler
- **Janela Lembrete:** 11:16:00 - 11:26:00 ✅ (ainda na janela)
- **Encontra tarefa:** `notification_sent=True` ❌
- **Ação:** Pula (já foi notificada)

#### 11:30:00 - Verificação do Scheduler
- **Janela Momento Exato:** 11:25:00 - 11:31:00 ✅ (tarefa às 11:30 está na janela)
- **Encontra tarefa:** `notification_sent=True` ❌
- **Ação:** Pula (já foi notificada no lembrete)

---

## 🐛 POR QUE RECEBEU 4 VEZES?

### Possíveis causas:

#### 1. **Race Condition (MAIS PROVÁVEL)**
- **Problema:** Duas verificações simultâneas antes de salvar `notification_sent=True`
- **Solução:** ✅ Implementado `select_for_update()` com `skip_locked=True`

#### 2. **Tarefa Entra em Ambas as Janelas**
- **Problema:** Se `due_date` está exatamente na borda, pode entrar nas duas janelas
- **Exemplo:** Tarefa às 11:30, verificação às 11:25 → entra no lembrete E no momento exato
- **Solução:** ✅ Filtro `notification_sent=False` em ambas as janelas

#### 3. **Múltiplas Instâncias do Scheduler**
- **Problema:** Várias threads rodando simultaneamente
- **Solução:** ✅ Flags `_scheduler_started` e `_recovery_started` implementadas

#### 4. **Retry do WhatsApp Duplicando**
- **Problema:** Se WhatsApp falha e retry, pode estar contando como nova notificação
- **Solução:** ✅ Retry não marca como nova notificação, apenas tenta novamente

#### 5. **WebSocket + WhatsApp Contando Separadamente**
- **Problema:** Se você recebe WebSocket E WhatsApp, pode parecer duplicado
- **Realidade:** São 2 tipos diferentes de notificação (navegador + WhatsApp)

---

## ✅ CORREÇÕES IMPLEMENTADAS

1. ✅ **`select_for_update()` com `skip_locked=True`** - Evita race condition
2. ✅ **Double-check antes de marcar `notification_sent=True`** - Evita duplicação
3. ✅ **Logs detalhados** - Mostra exatamente quem foi notificado
4. ✅ **Verificação de usuários duplicados** - Pula `created_by` se for mesmo de `assigned_to`
5. ✅ **Filtro `notification_sent=False` em ambas janelas** - Evita notificar duas vezes

---

## 📝 LOGS ESPERADOS (CORRETO)

```
📋 [TASK NOTIFICATIONS] Lembrete: Reunião com cliente (ID: xxx) - 24/11/2025 11:30:00
   👤 Assigned to: paulo.bernal@rbtec.com.br
   👤 Created by: paulo.bernal@rbtec.com.br
   📞 Contatos relacionados: 2
   📤 Notificando assigned_to: paulo.bernal@rbtec.com.br
✅ [TASK NOTIFICATIONS] Notificação no navegador (lembrete) enviada para paulo.bernal@rbtec.com.br
📤 [TASK NOTIFICATIONS] Enviando WhatsApp para +5517991253112 (usuário: paulo.bernal@rbtec.com.br)
✅ [TASK NOTIFICATIONS] WhatsApp enviado com sucesso para +5517991253112
   ⏭️ Pulando created_by (mesmo usuário de assigned_to)
📤 [TASK NOTIFICATIONS] Enviando WhatsApp para contato João (xxx)
✅ [TASK NOTIFICATIONS] WhatsApp enviado para contato João (xxx)
📤 [TASK NOTIFICATIONS] Enviando WhatsApp para contato Maria (xxx)
✅ [TASK NOTIFICATIONS] WhatsApp enviado para contato Maria (xxx)
✅ [TASK NOTIFICATIONS] Lembrete enviado (3 notificação(ões)) e marcado como notificado
```

**Total:** 3 notificações (1 para você + 2 para contatos) ✅

