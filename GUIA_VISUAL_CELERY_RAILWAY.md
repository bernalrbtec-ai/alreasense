# 🎨 **GUIA VISUAL: CRIAR CELERY WORKER NO RAILWAY**

## 📸 **PASSO A PASSO COM "CAPTURAS DE TELA"**

---

### **PASSO 1: CRIAR NOVO SERVIÇO**

```
┌─────────────────────────────────────────────────────┐
│  Railway - Projeto "ALREA Sense"                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [Backend]  [Frontend]  [PostgreSQL]  [Redis]       │
│                                                     │
│                      [ + New ]  ← CLIQUE AQUI       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Depois de clicar "+ New":**

```
┌─────────────────────────────────────────────────────┐
│  Add a new service                                  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ⚪ Empty Service                                   │
│  ⚪ Database                                        │
│  ⚫ GitHub Repo  ← SELECIONE ESTE                   │
│  ⚪ Docker Image                                    │
│                                                     │
│              [ Continue ]                           │
└─────────────────────────────────────────────────────┘
```

**Depois de clicar "Continue":**

```
┌─────────────────────────────────────────────────────┐
│  Select Repository                                  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  🔍 Search repositories...                          │
│                                                     │
│  ⚫ bernalrbtec-ai/alreasense  ← SELECIONE ESTE    │
│     (Same repository as Backend!)                  │
│                                                     │
│              [ Deploy ]                             │
└─────────────────────────────────────────────────────┘
```

**Vai pedir nome do serviço:**

```
┌─────────────────────────────────────────────────────┐
│  Service Name                                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Name: [ Celery Worker              ]              │
│                                                     │
│              [ Create ]                             │
└─────────────────────────────────────────────────────┘
```

**✅ Serviço criado!**

---

### **PASSO 2: CONFIGURAR ROOT DIRECTORY**

```
┌─────────────────────────────────────────────────────┐
│  Celery Worker                                      │
├─────────────────────────────────────────────────────┤
│  [Deployments]  [Variables]  [Settings]  [Metrics]  │
│                                                     │
│  Clique em → [Settings] ← AQUI                      │
└─────────────────────────────────────────────────────┘
```

**Na página Settings:**

```
┌─────────────────────────────────────────────────────┐
│  Settings                                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Environment                                        │
│  ├─ Root Directory                                  │
│  │  [ backend                    ]  ← DIGITE AQUI   │
│  │                                                  │
│  ├─ Start Command                                   │
│  │  [                            ]  ← VER PRÓXIMO   │
│  │                                                  │
│  └─ Build Command                                   │
│     [                            ]                  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

### **PASSO 3: CONFIGURAR START COMMAND**

```
┌─────────────────────────────────────────────────────┐
│  Settings                                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Environment                                        │
│  ├─ Root Directory                                  │
│  │  [ backend                    ]  ✅ JÁ TEM       │
│  │                                                  │
│  ├─ Start Command                                   │
│  │  [ celery -A alrea_sense      ]  ← DIGITE AQUI   │
│  │  [ worker --loglevel=info     ]                 │
│  │                                                  │
│  └─ Build Command                                   │
│     [ pip install -r requirements.txt ]            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**⚠️ IMPORTANTE: Comando EXATO:**
```
celery -A alrea_sense worker --loglevel=info
```

---

### **PASSO 4: CONFIGURAR VARIÁVEIS**

```
┌─────────────────────────────────────────────────────┐
│  Celery Worker                                      │
├─────────────────────────────────────────────────────┤
│  [Deployments]  [Variables]  [Settings]  [Metrics]  │
│                                                     │
│  Clique em → [Variables] ← AQUI                     │
└─────────────────────────────────────────────────────┘
```

**Na página Variables:**

```
┌─────────────────────────────────────────────────────┐
│  Variables                                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [ + New Variable ]                                 │
│                                                     │
│  (vazio - precisa adicionar)                        │
└─────────────────────────────────────────────────────┘
```

**Clique "+ New Variable":**

```
┌─────────────────────────────────────────────────────┐
│  Add Variable                                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ⚫ Variable  ⚪ Reference                           │
│                                                     │
│  Variable Name:  [ DATABASE_URL        ]            │
│  Variable Value: [ postgres://...      ]            │
│                                                     │
│  OU clique em [Reference] e selecione:             │
│  Service: Backend → Variable: DATABASE_URL         │
│                                                     │
│              [ Add ]                                │
└─────────────────────────────────────────────────────┘
```

**Repita para TODAS as variáveis:**
- DATABASE_URL ← do Backend
- REDIS_URL ← do Backend
- DJANGO_SECRET_KEY ← do Backend
- DJANGO_ALLOWED_HOSTS ← do Backend
- CORS_ALLOWED_ORIGINS ← do Backend
- DEBUG ← do Backend
- (todas as outras que o Backend tem)

**Depois de adicionar todas:**

```
┌─────────────────────────────────────────────────────┐
│  Variables                                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  DATABASE_URL        postgres://...        [Edit]  │
│  REDIS_URL           redis://...           [Edit]  │
│  DJANGO_SECRET_KEY   xxxxxxxx              [Edit]  │
│  DEBUG               True                  [Edit]  │
│  ...                                               │
│                                                     │
│  [ + New Variable ]                                │
└─────────────────────────────────────────────────────┘
```

---

### **PASSO 5: FAZER DEPLOY**

```
┌─────────────────────────────────────────────────────┐
│  Celery Worker                                      │
├─────────────────────────────────────────────────────┤
│  [Deployments]  [Variables]  [Settings]  [Metrics]  │
│                                                     │
│  Clique em → [Deployments] ← AQUI                   │
└─────────────────────────────────────────────────────┘
```

**Na página Deployments:**

```
┌─────────────────────────────────────────────────────┐
│  Deployments                                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  📦 Building...  (aguarde)                          │
│                                                     │
│  Ou se já terminou:                                │
│                                                     │
│  ✅ #1 - Oct 13, 2025 23:45                         │
│     Status: Success                                 │
│     Duration: 2m 34s                                │
│                                                     │
│     [ View Logs ]  ← CLIQUE PARA VER LOGS           │
└─────────────────────────────────────────────────────┘
```

---

### **PASSO 6: VERIFICAR LOGS**

**Depois de clicar "View Logs":**

```
┌─────────────────────────────────────────────────────┐
│  Logs - Deployment #1                               │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [2025-10-13 23:45:12] Installing dependencies...  │
│  [2025-10-13 23:45:15] Successfully installed       │
│  [2025-10-13 23:45:16] Starting celery worker...    │
│  [2025-10-13 23:45:17]                              │
│   -------------- celery@alrea-celery-worker v5.3.4  │
│  ---- **** -----                                    │
│  --- * ***  * -- Linux                              │
│  -- * - **** ---                                    │
│  - ** ---------- [config]                           │
│  - ** ---------- .> app:         alrea_sense:0x...  │
│  - ** ---------- .> transport:   redis://...        │
│  - ** ---------- .> results:     disabled://        │
│  - *** --- * --- .> concurrency: 4 (prefork)        │
│  -- ******* ---- .> task events: OFF                │
│  --- ***** -----                                    │
│                                                     │
│  [tasks]                                            │
│    . campaigns.tasks.process_campaign               │
│    . campaigns.tasks.send_single_message            │
│                                                     │
│  [INFO/MainProcess] Connected to redis://...        │
│  [INFO/MainProcess] mingle: searching for neighbors │
│  [INFO/MainProcess] mingle: all alone               │
│  [INFO/MainProcess] celery@... ready.  ← ✅ PRONTO! │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**✅ Se aparecer "ready." = FUNCIONANDO!**

**❌ Se aparecer erros, me manda que eu ajudo!**

---

### **PASSO 7: TESTAR**

**No PowerShell:**

```powershell
curl https://alreasense-backend-production.up.railway.app/api/health/ | ConvertFrom-Json | Select-Object -ExpandProperty celery
```

**Deve retornar:**

```
status    active_workers
------    --------------
healthy   1              ← ✅ FUNCIONANDO!
```

---

### **PASSO 8: TESTAR CAMPANHA**

```
1. Acesse: https://alreasense-production.up.railway.app
2. Faça login
3. Vá em "Campanhas"
4. Crie uma campanha de teste
5. Clique em "Iniciar"
6. Aguarde 10 segundos
7. Veja os logs do Celery Worker no Railway
```

**Deve aparecer nos logs:**

```
[2025-10-13 23:50:00] 🚀 Processando Campanha: Teste
[2025-10-13 23:50:01] 📊 Lote processado:
[2025-10-13 23:50:01]    ✅ Enviadas: 1
[2025-10-13 23:50:01]    ❌ Falhas: 0
```

**✅ Se aparecer isso = CAMPANHAS FUNCIONANDO! 🎉**

---

## 🎯 **ESTRUTURA FINAL NO RAILWAY:**

```
┌─────────────────────────────────────────────────────┐
│  Railway - Projeto "ALREA Sense"                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  📦 Backend          📦 Celery Worker  ⭐ NOVO!     │
│     Django                Processar tasks           │
│     Port: 8000            (sem porta)               │
│                                                     │
│  📦 Frontend         📦 PostgreSQL                  │
│     React                 Banco de dados            │
│     Port: 3000                                      │
│                                                     │
│                      📦 Redis                       │
│                          Fila de tasks              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 📋 **RESUMO:**

```
✅ 1. Criar serviço "Celery Worker" (mesmo repo)
✅ 2. Root Directory: backend
✅ 3. Start Command: celery -A alrea_sense worker --loglevel=info
✅ 4. Variables: Copiar TODAS do Backend
✅ 5. Deploy e aguardar 2-3 min
✅ 6. Ver logs: "celery@... ready."
✅ 7. Testar health check: "healthy"
✅ 8. Testar campanha: envia mensagens!
```

**Tempo total: ~10 minutos** ⏱️

---

**📄 Criado: `GUIA_VISUAL_CELERY_RAILWAY.md`**

