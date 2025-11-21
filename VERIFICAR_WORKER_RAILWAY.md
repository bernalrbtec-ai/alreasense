# 🔍 Como Verificar Workers no Railway

## 📊 **MÉTODO 1: Dashboard Railway (Recomendado)**

### **Passo 1: Acessar Logs do Worker**

1. Acesse https://railway.app
2. Entre no projeto **"ALREA Sense"**
3. Clique no serviço **"backend"**
4. Vá na aba **"Deployments"**
5. Clique no deployment mais recente (status: **"Active"**)
6. Na seção **"Logs"**, procure por logs do processo `worker_tasks`

### **Passo 2: O que procurar nos logs**

**✅ Worker RODANDO (sucesso):**
```
🔔 [WORKER TASKS] ==========================================
🔔 [WORKER TASKS] INICIANDO TASK NOTIFICATIONS - 2025-11-21 09:00:00
🔔 [WORKER TASKS] ==========================================
📋 [WORKER TASKS] Verificador de notificações de tarefas
⏰ Intervalo: 60 segundos
📅 Janela de notificação: 15 minutos antes
🔔 [TASK NOTIFICATIONS] Verificando tarefas entre 2025-11-21 09:15:00 e 2025-11-21 09:16:00
📋 [TASK NOTIFICATIONS] Encontradas 0 tarefa(s) para notificar
```

**❌ Worker NÃO está rodando:**
- Não aparece nenhum log com `[WORKER TASKS]`
- Ou aparece erro como:
  ```
  ❌ Erro no loop principal: ...
  ```

---

## 🔍 **MÉTODO 2: Verificar Processos Ativos**

### **No Railway Dashboard:**

1. Vá no serviço **"backend"**
2. Clique em **"Settings"**
3. Procure por **"Processes"** ou **"Metrics"**
4. Deve mostrar 4 processos:
   - ✅ `web` (Daphne - servidor web)
   - ✅ `worker_chat` (Chat consumer)
   - ✅ `worker_campaigns` (Campaigns consumer)
   - ✅ `worker_tasks` (Task notifications) ← **ESTE!**

**Se `worker_tasks` não aparece, o worker não está rodando!**

---

## 📋 **MÉTODO 3: Verificar Procfile**

O `Procfile` deve ter a linha:

```
worker_tasks: cd backend && echo "🔔 [WORKER TASKS]..." && python manage.py check_task_notifications
```

**Verificar:**
1. No Railway, vá em **"Settings"** do serviço backend
2. Procure por **"Start Command"** ou **"Procfile"**
3. Deve listar todos os processos, incluindo `worker_tasks`

---

## 🧪 **MÉTODO 4: Testar Manualmente**

### **Criar uma tarefa de teste:**

1. Acesse o dashboard
2. Crie uma tarefa agendada para **15 minutos no futuro**
3. Aguarde 1-2 minutos
4. Verifique os logs do `worker_tasks`
5. Deve aparecer:
   ```
   📋 [TASK NOTIFICATIONS] Encontradas 1 tarefa(s) para notificar
   ✅ 1 tarefa(s) notificada(s)
   ```

---

## ⚠️ **PROBLEMAS COMUNS**

### **1. Worker não aparece nos logs**

**Causa:** Worker não está rodando ou Procfile não está configurado

**Solução:**
1. Verificar se `Procfile` tem a linha `worker_tasks:`
2. Fazer redeploy:
   ```bash
   git commit --allow-empty -m "chore: force redeploy workers"
   git push
   ```

### **2. Worker aparece mas não notifica**

**Causa:** Tarefas não estão na janela de notificação (15 min antes)

**Solução:**
1. Verificar logs: `📋 [TASK NOTIFICATIONS] Encontradas X tarefa(s)`
2. Se `X = 0`, não há tarefas na janela
3. Criar tarefa para 15-16 minutos no futuro

### **3. Worker para de funcionar após deploy**

**Causa:** Worker não reinicia automaticamente

**Solução:**
1. No Railway Dashboard → **"Settings"** → **"Restart"**
2. Ou fazer novo deploy

---

## 📊 **ESTRUTURA ESPERADA NO RAILWAY**

```
Railway - Projeto "ALREA Sense"
└── Service: backend
    ├── Process: web (Daphne)
    ├── Process: worker_chat (Chat consumer)
    ├── Process: worker_campaigns (Campaigns consumer)
    └── Process: worker_tasks (Task notifications) ← VERIFICAR ESTE!
```

---

## ✅ **CHECKLIST RÁPIDO**

- [ ] Worker aparece nos logs com `[WORKER TASKS]`
- [ ] Logs mostram verificações a cada 60 segundos
- [ ] Logs mostram "Encontradas X tarefa(s)" quando há tarefas
- [ ] Processo `worker_tasks` aparece em "Processes" ou "Metrics"
- [ ] Procfile tem a linha `worker_tasks:`

---

## 🎯 **RESUMO**

**Para verificar se o worker está rodando:**

1. **Railway Dashboard** → **backend** → **Deployments** → **Logs**
2. Procurar por: `🔔 [WORKER TASKS]` ou `[TASK NOTIFICATIONS]`
3. Se aparecer = ✅ **Worker está rodando!**
4. Se não aparecer = ❌ **Worker não está rodando!**

**Para verificar se está funcionando:**

1. Criar tarefa para 15 minutos no futuro
2. Aguardar 1-2 minutos
3. Verificar logs: deve aparecer "Encontradas 1 tarefa(s)"
4. Se aparecer = ✅ **Worker está funcionando!**

