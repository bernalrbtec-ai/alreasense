# 🧪 **TESTE: CELERY WORKER NO RAILWAY**

## ✅ **VERIFICAR SE ESTÁ CORRETO:**

### **1. Veja os logs do Celery Worker:**

**Railway → Celery Worker → Deployments → [Deployment ativo] → Logs**

**Deve aparecer:**
```
 -------------- celery@alrea-celery-worker v5.x.x
---- **** ----- 
--- * ***  * -- Linux
-- * - **** --- 
- ** ---------- [config]
- ** ---------- .> app:         alrea_sense:0x...
- ** ---------- .> transport:   redis://...
- ** ---------- .> results:     disabled://
- *** --- * --- .> concurrency: 4 (prefork)
-- ******* ---- .> task events: OFF
--- ***** ----- 

[tasks]
  . campaigns.tasks.process_campaign
  . campaigns.tasks.send_single_message

[INFO/MainProcess] Connected to redis://...
[INFO/MainProcess] mingle: searching for neighbors
[INFO/MainProcess] mingle: all alone
[INFO/MainProcess] celery@alrea-celery-worker ready.
```

**✅ Se aparecer isso = CELERY FUNCIONANDO!**

---

**❌ Se aparecer isso, está ERRADO:**
```
[INFO] Listening at: http://0.0.0.0:8000
[INFO] Using worker: sync
[INFO] Booting worker with pid: 1234
```
**= Está rodando Django! Verifique o Start Command!**

---

### **2. Teste o health check:**

```powershell
curl https://alreasense-backend-production.up.railway.app/api/health/ | ConvertFrom-Json | Select-Object -ExpandProperty celery
```

**Deve retornar:**
```
status    active_workers
------    --------------
healthy   1
```

**✅ Se retornar `healthy` e `active_workers: 1` = FUNCIONANDO!**

**❌ Se retornar `unhealthy` e `No workers available` = NÃO FUNCIONANDO!**

---

### **3. Teste uma campanha:**

1. Acesse https://alreasense-production.up.railway.app
2. Vá em "Campanhas"
3. Crie uma campanha de teste
4. Clique em "Iniciar"
5. **Aguarde 5-10 segundos**
6. Veja os logs do Celery Worker no Railway

**Deve aparecer nos logs:**
```
🚀 Processando Campanha: Nome da Campanha
📊 Lote processado:
   ✅ Enviadas: 1
   ❌ Falhas: 0
   ⏭️ Puladas: 0
```

**✅ Se aparecer isso = CAMPANHA ENVIANDO MENSAGENS!**

---

## 🔧 **SE NÃO FUNCIONAR:**

### **Problema 1: Logs mostram Django ao invés de Celery**

**Causa:** Start Command errado

**Solução:**
1. Railway → Celery Worker → Settings → Start Command
2. Deve estar EXATAMENTE:
   ```bash
   celery -A alrea_sense worker --loglevel=info
   ```
3. Se estiver diferente, corrija e faça "Redeploy"

---

### **Problema 2: Erro "No module named 'alrea_sense'"**

**Causa:** Root Directory errado

**Solução:**
1. Railway → Celery Worker → Settings → Root Directory
2. Deve estar: `backend`
3. Se estiver vazio ou diferente, corrija e faça "Redeploy"

---

### **Problema 3: Health check retorna "unhealthy"**

**Causa:** Celery não está conectando no Redis

**Solução:**
1. Verifique se variável `REDIS_URL` está configurada
2. Verifique se o Redis está rodando no Railway
3. Verifique os logs do Celery Worker para erros de conexão

---

## ✅ **CHECKLIST FINAL:**

```
[ ] Logs mostram "celery@... ready."
[ ] Logs NÃO mostram "Listening at http://"
[ ] Logs mostram tasks registradas
[ ] Health check retorna "healthy"
[ ] Health check mostra "active_workers: 1"
[ ] Campanha processa mensagens nos logs
[ ] Mensagens são enviadas de verdade
```

**Se todos marcados = CELERY FUNCIONANDO 100%!** 🎉

---

## 📊 **DIFERENÇA ENTRE BACKEND E CELERY:**

### **Backend (Django):**
```
Start: gunicorn alrea_sense.wsgi:application --bind 0.0.0.0:$PORT
Logs:  Listening at: http://0.0.0.0:8000
       Using worker: sync
       Booting worker with pid: 1234

Função: Servidor HTTP
        Responde requisições API
        Porta: 8000
```

### **Celery Worker:**
```
Start: celery -A alrea_sense worker --loglevel=info
Logs:  celery@alrea-celery-worker ready.
       Connected to redis://...
       [tasks] . campaigns.tasks.process_campaign

Função: Worker background
        Processa tasks assíncronas
        Porta: NENHUMA (não é HTTP)
```

**SÃO COMPLETAMENTE DIFERENTES!** ✅

---

**📄 Criado: `TESTE_CELERY_RAILWAY.md`**

