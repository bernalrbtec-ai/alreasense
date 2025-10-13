# ✅ **CHECKLIST: CELERY WORKER NO RAILWAY**

## 📋 **CONFIGURAÇÃO:**

```
[ ] 1. Criar novo serviço "Celery Worker"
       Railway → + New → GitHub Repo → bernalrbtec-ai/alreasense

[ ] 2. Configurar Root Directory
       Settings → Root Directory → backend

[ ] 3. Configurar Start Command
       Settings → Start Command → 
       celery -A alrea_sense worker --loglevel=info

[ ] 4. Copiar variáveis do Backend
       Variables → Copiar TODAS do serviço Backend:
       - DATABASE_URL
       - REDIS_URL
       - DJANGO_SECRET_KEY
       - DJANGO_ALLOWED_HOSTS
       - CORS_ALLOWED_ORIGINS
       - DEBUG
       - (todas as outras)

[ ] 5. Deploy
       Deployments → Deploy → Aguardar 2-3 min

[ ] 6. Verificar logs
       Deployments → [Ativo] → Logs →
       Procurar: "celery@... ready."

[ ] 7. Testar health check
       PowerShell:
       curl https://alreasense-backend-production.up.railway.app/api/health/
       
       Deve retornar: "status": "healthy"

[ ] 8. Testar campanha
       - Criar campanha
       - Iniciar
       - Verificar se envia mensagens
```

---

## 🎯 **ESTRUTURA FINAL:**

```
Railway - Projeto "ALREA Sense"
├── Backend (Django)
│   ├── Root: backend/
│   ├── Start: daphne -b 0.0.0.0 -p $PORT alrea_sense.asgi:application
│   └── Porta: 8000 (pública)
│
├── Celery Worker ⭐ NOVO!
│   ├── Root: backend/  ← MESMO código!
│   ├── Start: celery -A alrea_sense worker --loglevel=info
│   └── Porta: Nenhuma (não precisa)
│
├── Frontend (React)
│   ├── Root: frontend/
│   ├── Start: serve -s dist
│   └── Porta: 3000 (pública)
│
├── PostgreSQL
│   └── Banco de dados (compartilhado)
│
└── Redis
    └── Fila de tasks (compartilhado)
```

---

## ⚠️ **ERROS COMUNS:**

### **1. Logs mostram Django ao invés de Celery**

**Erro:** Logs mostram "Listening at http://0.0.0.0:8000"

**Causa:** Start Command errado

**Solução:** 
- Settings → Start Command
- Deve ser EXATAMENTE: `celery -A alrea_sense worker --loglevel=info`

---

### **2. ModuleNotFoundError: No module named 'alrea_sense'**

**Erro:** Celery não encontra o módulo

**Causa:** Root Directory errado

**Solução:**
- Settings → Root Directory
- Deve ser: `backend`

---

### **3. Cannot connect to redis**

**Erro:** Celery não conecta no Redis

**Causa:** Variável REDIS_URL não configurada

**Solução:**
- Variables → Adicionar REDIS_URL
- Copiar do serviço Backend

---

### **4. Health check retorna "unhealthy"**

**Erro:** `curl /api/health/` mostra "No workers available"

**Causa:** Celery não está rodando ou não conectou

**Solução:**
1. Verificar logs do Celery Worker
2. Procurar erros
3. Verificar se variáveis estão corretas
4. Verificar se Redis está rodando

---

## 🧪 **TESTE FINAL:**

```powershell
# PowerShell
curl https://alreasense-backend-production.up.railway.app/api/health/ | ConvertFrom-Json | Select-Object -ExpandProperty celery
```

**✅ Sucesso:**
```
status    active_workers
------    --------------
healthy   1
```

**❌ Falha:**
```
status    error
------    -----
unhealthy No workers available
```

---

## 📊 **COMPARAÇÃO VISUAL:**

### **ANTES (Sem Celery Worker):**
```
Campanhas:
1. Clica "Iniciar" → Status: running ✅
2. Aguarda... ⏳
3. Aguarda... ⏳
4. Aguarda... ⏳
5. Nada acontece! ❌
```

### **DEPOIS (Com Celery Worker):**
```
Campanhas:
1. Clica "Iniciar" → Status: running ✅
2. Celery pega a task ✅
3. Envia primeira mensagem ✅
4. Aguarda intervalo ✅
5. Envia próxima mensagem ✅
6. FUNCIONA! 🎉
```

---

## 💰 **CUSTO:**

```
Antes:
- Backend: ~$5/mês
- PostgreSQL: ~$5/mês
- Redis: ~$5/mês
Total: ~$15/mês

Depois:
- Backend: ~$5/mês
- Celery Worker: ~$5/mês  ← +1 serviço
- PostgreSQL: ~$5/mês
- Redis: ~$5/mês
Total: ~$20/mês

+$5/mês para campanhas funcionarem ✅
```

---

## 🎯 **RESUMO:**

```
┌────────────────────────────────────────┐
│  1. Criar serviço "Celery Worker"      │
│  2. Root: backend                      │
│  3. Start: celery worker               │
│  4. Variáveis: copiar do Backend       │
│  5. Deploy                             │
│  6. Verificar logs: "ready."           │
│  7. Testar health check                │
│  8. Testar campanha                    │
│                                        │
│  Tempo total: ~10 minutos              │
└────────────────────────────────────────┘
```

---

**📄 Criado: `CHECKLIST_CELERY_RAILWAY.md`**

