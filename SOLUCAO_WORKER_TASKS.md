# ✅ SOLUÇÃO DEFINITIVA: Worker de Tarefas no Railway

## ❌ **PROBLEMA CONFIRMADO:**

O `worker_tasks` **NÃO está rodando** no Railway. Nos logs aparecem:
- ✅ `web` (Daphne)
- ✅ `worker_chat`
- ✅ `worker_campaigns`
- ❌ `worker_tasks` - **NÃO aparece!**

**Consequência:** Notificações de tarefas não são enviadas.

---

## ✅ **SOLUÇÃO: Criar Serviço Separado no Railway**

O Railway pode não iniciar todos os processos do Procfile automaticamente. A solução é criar um serviço separado.

### **Passo a Passo:**

1. **Acesse Railway Dashboard**
   - https://railway.app
   - Entre no projeto "ALREA Sense"

2. **Criar Novo Serviço**
   - Clique em **"+ New"** (canto superior direito)
   - Selecione **"Service"**
   - Escolha **"GitHub Repo"**
   - Selecione o repositório: `bernalrbtec-ai/alreasense`
   - Clique em **"Deploy"**

3. **Configurar o Serviço**
   
   **Nome do Serviço:**
   - Mude para: `task-notifications-worker` (ou qualquer nome descritivo)

   **Settings → Root Directory:**
   - Digite: `backend`

   **Settings → Start Command:**
   - Digite: `python manage.py check_task_notifications`
   - **IMPORTANTE:** Não incluir `cd backend` aqui, pois já está no Root Directory

4. **Configurar Variáveis de Ambiente**
   
   **Variables → Copiar do Backend:**
   - Clique em **"Variables"**
   - Clique em **"New Variable"** para cada uma abaixo
   - **OU** use a opção de copiar do serviço Backend (se disponível)
   
   **Variáveis necessárias:**
   - `DATABASE_URL` (copiar do Backend)
   - `REDIS_URL` (copiar do Backend)
   - `DJANGO_SECRET_KEY` (copiar do Backend)
   - `DJANGO_ALLOWED_HOSTS` (copiar do Backend)
   - `CORS_ALLOWED_ORIGINS` (copiar do Backend)
   - `DEBUG` (copiar do Backend)
   - `RABBITMQ_URL` (copiar do Backend)
   - `S3_ENDPOINT_URL` (copiar do Backend)
   - `S3_ACCESS_KEY` (copiar do Backend)
   - `S3_SECRET_KEY` (copiar do Backend)
   - `S3_BUCKET` (copiar do Backend)
   - `S3_REGION` (copiar do Backend)
   - **TODAS as outras variáveis do Backend**

   **💡 Dica:** Se o Railway tiver opção "Copy from Service", use para copiar todas de uma vez do serviço Backend.

5. **Deploy**
   - Clique em **"Deploy"** ou aguarde deploy automático
   - Aguarde 2-3 minutos

6. **Verificar Logs**
   
   Após o deploy, vá em **"Deployments"** → **Deployment ativo** → **"Logs"**
   
   **Deve aparecer:**
   ```
   🔔 [WORKER TASKS] ==========================================
   🔔 [WORKER TASKS] INICIANDO TASK NOTIFICATIONS - [data]
   ⏰ Intervalo: 60 segundos
   📅 Janela de notificação: 15 minutos antes
   🔔 [TASK NOTIFICATIONS] Verificando tarefas entre...
   📋 [TASK NOTIFICATIONS] Encontradas X tarefa(s) para notificar
   ```

---

## 🧪 **TESTAR SE FUNCIONOU:**

1. **Criar Tarefa de Teste**
   - Acesse o dashboard
   - Crie uma tarefa agendada para **15 minutos no futuro**
   - Aguarde 1-2 minutos

2. **Verificar Logs do Worker**
   - Railway → `task-notifications-worker` → Deployments → Logs
   - Deve aparecer: `📋 [TASK NOTIFICATIONS] Encontradas 1 tarefa(s) para notificar`
   - Deve aparecer: `✅ 1 tarefa(s) notificada(s)`

3. **Verificar Notificação**
   - Se o usuário tem `notify_whatsapp=True` e telefone configurado, deve receber WhatsApp
   - Deve aparecer notificação no navegador (se estiver conectado)

---

## 📊 **ESTRUTURA FINAL NO RAILWAY:**

```
Railway - Projeto "ALREA Sense"
├── backend (Django + Daphne)
│   ├── Process: web ✅
│   ├── Process: worker_chat ✅
│   └── Process: worker_campaigns ✅
│
├── task-notifications-worker ⭐ NOVO!
│   ├── Root: backend/
│   ├── Start: python manage.py check_task_notifications
│   └── Variables: Todas do Backend
│
├── frontend (React)
├── postgres (Database)
├── redis (Cache)
└── rabbitmq (Queue)
```

---

## ⚠️ **ERROS COMUNS:**

### **1. "ModuleNotFoundError: No module named 'django'"**

**Causa:** Root Directory errado

**Solução:**
- Settings → Root Directory → `backend`

### **2. "Cannot connect to database"**

**Causa:** Variáveis de ambiente não configuradas

**Solução:**
- Variables → Copiar `DATABASE_URL` do Backend

### **3. "Command not found: python"**

**Causa:** Python não está no PATH

**Solução:**
- Start Command → `python3 manage.py check_task_notifications`
- OU verificar se Railway detecta Python automaticamente

### **4. Logs não aparecem**

**Causa:** Processo pode estar crashando silenciosamente

**Solução:**
- Verificar logs completos (não apenas últimas linhas)
- Verificar se há erros de importação ou configuração

---

## ✅ **CHECKLIST FINAL:**

- [ ] Serviço `task-notifications-worker` criado
- [ ] Root Directory: `backend`
- [ ] Start Command: `python manage.py check_task_notifications`
- [ ] Todas as variáveis do Backend copiadas
- [ ] Deploy concluído com sucesso
- [ ] Logs mostram `[WORKER TASKS] INICIANDO`
- [ ] Logs mostram verificações a cada 60 segundos
- [ ] Tarefa de teste criada e notificada

---

## 🎯 **RESUMO:**

**O problema:** Railway não inicia o processo `worker_tasks` do Procfile automaticamente.

**A solução:** Criar um serviço separado no Railway com:
- Root Directory: `backend`
- Start Command: `python manage.py check_task_notifications`
- Variáveis: Todas do Backend

**Após isso, as notificações de tarefas devem funcionar!** ✅

