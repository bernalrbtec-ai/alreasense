# 📋 FLUXO COMPLETO DE NOTIFICAÇÕES DE TAREFAS

## 🔄 CICLO DE VERIFICAÇÃO

O scheduler roda **a cada 60 segundos** e verifica duas janelas:

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

## ✅ CORREÇÕES NECESSÁRIAS

1. **Usar `select_for_update()` para evitar race condition**
2. **Melhorar lógica de janelas para evitar sobreposição**
3. **Adicionar log detalhado de cada notificação enviada**
4. **Verificar se retry está duplicando notificações**

