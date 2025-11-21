# 🔧 Como Corrigir Worker de Tarefas no Railway

## ❌ **PROBLEMA IDENTIFICADO:**

Nos logs do backend **NÃO aparecem** logs do `worker_tasks`:
- ✅ `web` (Daphne) - aparece
- ✅ `worker_chat` - aparece  
- ✅ `worker_campaigns` - aparece
- ❌ `worker_tasks` - **NÃO aparece!**

**Consequência:** Notificações de tarefas não são enviadas!

---

## 🔍 **VERIFICAÇÃO 1: Railway Dashboard**

### **Passo 1: Verificar Processos Ativos**

1. Acesse https://railway.app
2. Vá no serviço **"backend"**
3. Clique em **"Deployments"**
4. Abra o deployment ativo
5. Procure por **"Processes"** ou **"Metrics"**

**Deve mostrar 4 processos:**
- ✅ `web`
- ✅ `worker_chat`
- ✅ `worker_campaigns`
- ❌ `worker_tasks` ← **Este pode estar faltando!**

### **Passo 2: Verificar Logs Separados**

No Railway, cada processo do Procfile pode ter logs separados:

1. No deployment ativo, procure por **abas de logs** ou **filtros**
2. Tente filtrar por `worker_tasks`
3. Se não aparecer nada = **processo não está rodando**

---

## ✅ **SOLUÇÃO 1: Verificar Configuração do Railway**

### **Opção A: Railway pode não iniciar todos os processos automaticamente**

Algumas versões do Railway requerem configuração manual para múltiplos processos.

**Verificar:**
1. Railway → Backend → **Settings**
2. Procure por **"Processes"** ou **"Start Command"**
3. Se houver opção para habilitar processos, verifique se `worker_tasks` está marcado

### **Opção B: Criar Serviço Separado (Recomendado)**

Se o Railway não iniciar automaticamente, criar um serviço separado:

1. Railway → **"+ New"** → **"Service"**
2. Selecione **"GitHub Repo"**
3. Escolha o mesmo repositório
4. Nome: **"Task Notifications Worker"**

**Configurar:**
- **Root Directory:** `backend`
- **Start Command:** 
  ```bash
  python manage.py check_task_notifications
  ```
- **Variables:** Copiar TODAS do serviço Backend

---

## ✅ **SOLUÇÃO 2: Verificar Procfile**

O `Procfile` está correto, mas vamos garantir:

```procfile
web: cd backend && ... && daphne ...
worker_chat: cd backend && ... && python manage.py start_chat_consumer
worker_campaigns: cd backend && ... && python manage.py start_rabbitmq_consumer
worker_tasks: cd backend && echo "🔔 [WORKER TASKS]..." && python manage.py check_task_notifications
```

**Verificar:**
1. O arquivo `Procfile` está na raiz do projeto?
2. Está commitado no Git?
3. O Railway está usando este Procfile?

---

## ✅ **SOLUÇÃO 3: Testar Localmente**

Para confirmar que o comando funciona:

```bash
cd backend
python manage.py check_task_notifications --run-once
```

**Deve mostrar:**
```
🔔 [TASK NOTIFICATIONS] Verificando tarefas entre...
📋 [TASK NOTIFICATIONS] Encontradas X tarefa(s) para notificar
```

Se funcionar localmente, o problema é apenas no Railway.

---

## 🧪 **TESTE RÁPIDO: Forçar Log Inicial**

Vamos adicionar um log mais cedo no comando para garantir que aparece:

O comando já tem logs no início:
```python
self.stdout.write('🔔 Iniciando verificador de notificações de tarefas...')
```

Se este log não aparece, o processo não está sendo iniciado.

---

## 📊 **ESTRUTURA ESPERADA NO RAILWAY**

```
Railway - Projeto "ALREA Sense"
└── Service: backend
    ├── Process: web ✅ (aparece nos logs)
    ├── Process: worker_chat ✅ (aparece nos logs)
    ├── Process: worker_campaigns ✅ (aparece nos logs)
    └── Process: worker_tasks ❌ (NÃO aparece nos logs!)
```

---

## ⚡ **SOLUÇÃO RÁPIDA: Criar Serviço Separado**

**Passo a passo:**

1. **Railway Dashboard** → **"+ New"** → **"Service"**
2. **GitHub Repo** → escolher `bernalrbtec-ai/alreasense`
3. **Nome:** `task-notifications-worker`
4. **Settings:**
   - **Root Directory:** `backend`
   - **Start Command:** `python manage.py check_task_notifications`
5. **Variables:** Copiar TODAS do serviço Backend
6. **Deploy**

**Após deploy, verificar logs:**
```
🔔 [WORKER TASKS] ==========================================
🔔 [WORKER TASKS] INICIANDO TASK NOTIFICATIONS - [data]
⏰ Intervalo: 60 segundos
📅 Janela de notificação: 15 minutos antes
```

---

## 🔍 **DIAGNÓSTICO: Por que não aparece?**

**Possíveis causas:**

1. **Railway não inicia todos os processos do Procfile automaticamente**
   - Solução: Criar serviço separado

2. **Processo está crashando imediatamente**
   - Verificar logs de erro
   - Testar comando localmente

3. **Procfile não está sendo usado**
   - Verificar se Railway está configurado para usar Procfile
   - Verificar se há "Start Command" customizado sobrescrevendo

4. **Limite de processos no plano Railway**
   - Alguns planos limitam número de processos
   - Verificar plano atual

---

## ✅ **CHECKLIST DE VERIFICAÇÃO**

- [ ] Procfile tem linha `worker_tasks:`
- [ ] Procfile está na raiz do projeto
- [ ] Procfile está commitado no Git
- [ ] Railway mostra 4 processos (ou serviço separado criado)
- [ ] Logs mostram `[WORKER TASKS]` ou `[TASK NOTIFICATIONS]`
- [ ] Comando funciona localmente (`--run-once`)
- [ ] Variáveis de ambiente estão configuradas

---

## 🎯 **PRÓXIMOS PASSOS**

1. **Verificar Railway Dashboard** → ver se `worker_tasks` aparece em processos
2. **Se não aparecer** → criar serviço separado
3. **Se aparecer mas não funciona** → verificar logs de erro
4. **Testar** → criar tarefa para 15 min no futuro e aguardar notificação

