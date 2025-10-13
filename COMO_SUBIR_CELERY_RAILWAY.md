# 🚀 **COMO SUBIR CELERY WORKER NO RAILWAY**

## ❌ **PROBLEMA ATUAL:**

```
Celery Status: unhealthy
Error: No workers available
```

**Consequência:** Campanhas ficam em "running" mas nunca enviam mensagens!

---

## ✅ **SOLUÇÃO: ADICIONAR SERVIÇO CELERY NO RAILWAY**

### **Passo 1: Criar novo serviço no Railway**

1. Acesse https://railway.app
2. Entre no projeto "ALREA Sense"
3. Clique em **"+ New"** → **"Service"**
4. Selecione **"GitHub Repo"**
5. Escolha o mesmo repositório (bernalrbtec-ai/alreasense)
6. Nome do serviço: **"Celery Worker"**

---

### **Passo 2: Configurar variáveis de ambiente**

**No serviço "Celery Worker", aba "Variables":**

Copie TODAS as variáveis do serviço "Backend":
- `DATABASE_URL`
- `REDIS_URL`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `DEBUG`
- Todas as outras...

**IMPORTANTE:** Use as MESMAS variáveis do Backend!

---

### **Passo 3: Configurar comando de start**

**No serviço "Celery Worker", aba "Settings":**

1. **Start Command:**
   ```bash
   celery -A alrea_sense worker --loglevel=info
   ```

2. **Root Directory:** (deixar vazio ou `backend/`)

3. **Build Command:** (deixar padrão)

---

### **Passo 4: Deploy**

1. Clique em **"Deploy"**
2. Aguarde o build e deploy
3. Verifique os logs:
   ```
   [2025-10-13 ...] [INFO/MainProcess] Connected to redis://...
   [2025-10-13 ...] [INFO/MainProcess] celery@... ready.
   ```

4. Se aparecer "ready" = **Celery funcionando!** ✅

---

## 🧪 **TESTAR SE FUNCIONOU:**

### **1. Verificar health check:**

```powershell
curl https://alreasense-backend-production.up.railway.app/api/health/ | ConvertFrom-Json | Select-Object -ExpandProperty celery
```

**Deve retornar:**
```
status    active_workers
------    -------------
healthy   1
```

### **2. Iniciar uma campanha:**

1. Acesse https://alreasense-production.up.railway.app
2. Vá em "Campanhas"
3. Inicie uma campanha de teste
4. **Deve começar a enviar mensagens!** ✅

### **3. Ver logs do Celery Worker:**

```
Railway → Celery Worker → Deployments → [Ativo] → Logs
```

**Procure por:**
```
🚀 Processando Campanha: Nome da Campanha
📊 Lote processado:
   ✅ Enviadas: 1
```

---

## 🔧 **ALTERNATIVA: USAR CELERY BEAT (Para agendamentos)**

Se quiser agendar campanhas para rodar em horário específico:

### **Criar serviço "Celery Beat":**

1. **Novo serviço no Railway**
2. **Nome:** "Celery Beat"
3. **Start Command:**
   ```bash
   celery -A alrea_sense beat --loglevel=info
   ```
4. **Variáveis:** Mesmas do Backend

---

## 📋 **ESTRUTURA FINAL NO RAILWAY:**

```
┌────────────────────────────────────┐
│  Projeto: ALREA Sense              │
├────────────────────────────────────┤
│  1. Backend (Django)               │
│     Start: gunicorn ...            │
│                                    │
│  2. Frontend (React)               │
│     Start: serve -s dist           │
│                                    │
│  3. Celery Worker ⭐ NOVO!         │
│     Start: celery -A alrea_sense   │
│            worker --loglevel=info  │
│                                    │
│  4. PostgreSQL (Banco)             │
│                                    │
│  5. Redis (Cache/Queue)            │
└────────────────────────────────────┘
```

---

## ⚡ **QUICKFIX TEMPORÁRIO (Se não quiser criar serviço agora):**

### **Rodar Celery no próprio Backend (não recomendado):**

1. Railway → Backend → Settings → Start Command
2. Mudar de:
   ```bash
   gunicorn alrea_sense.wsgi:application --bind 0.0.0.0:$PORT
   ```
   
   Para:
   ```bash
   sh -c "celery -A alrea_sense worker --loglevel=info --detach && gunicorn alrea_sense.wsgi:application --bind 0.0.0.0:$PORT"
   ```

**⚠️ Desvantagens:**
- Menos recursos para o Django
- Se reiniciar, tasks em processamento são perdidas
- Não escalável

**✅ Recomendação:** Use serviço separado!

---

## 🐛 **TROUBLESHOOTING:**

### **1. Celery não conecta no Redis:**

**Erro:**
```
[ERROR/MainProcess] consumer: Cannot connect to redis://...
```

**Solução:**
- Verifique se `REDIS_URL` está configurado
- Verifique se o Redis está rodando no Railway

---

### **2. Celery não encontra o app:**

**Erro:**
```
ModuleNotFoundError: No module named 'alrea_sense'
```

**Solução:**
- Verifique se o **Root Directory** está correto
- Deve ser `backend/` ou vazio (dependendo da estrutura)

---

### **3. Tasks não aparecem:**

**Erro:**
```
[WARNING] No tasks registered
```

**Solução:**
- Verifique se `backend/apps/campaigns/tasks.py` existe
- Verifique se tem `@shared_task` nas funções
- Reinicie o Celery Worker

---

## 📊 **VERIFICAR SE ESTÁ FUNCIONANDO:**

### **Health Check:**
```powershell
curl https://alreasense-backend-production.up.railway.app/api/health/
```

**Deve mostrar:**
```json
{
  "celery": {
    "status": "healthy",
    "active_workers": 1
  }
}
```

### **Logs do Worker:**
```
Railway → Celery Worker → Logs
```

**Procure por:**
```
[INFO/MainProcess] celery@... ready.
[INFO/MainProcess] Task campaigns.tasks.process_campaign received
🚀 Processando Campanha: ...
```

---

## 🎯 **RESUMO:**

```
┌────────────────────────────────────────┐
│  PROBLEMA: Celery não está rodando     │
│  CAUSA: Sem worker no Railway          │
│  SOLUÇÃO: Criar serviço Celery Worker  │
│                                        │
│  Passos:                               │
│  1. Railway → + New → Service          │
│  2. Copiar variáveis do Backend        │
│  3. Start Command:                     │
│     celery -A alrea_sense worker       │
│  4. Deploy                             │
│  5. Testar campanha                    │
│                                        │
│  Tempo: ~10 minutos                    │
└────────────────────────────────────────┘
```

---

**📄 Criado: `COMO_SUBIR_CELERY_RAILWAY.md`**

