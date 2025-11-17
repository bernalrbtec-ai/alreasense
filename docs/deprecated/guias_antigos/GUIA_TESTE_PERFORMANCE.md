# 🧪 GUIA DE TESTES - OTIMIZAÇÕES DE PERFORMANCE

> **O que testar:** Cache, Queries, Índices, Performance geral  
> **Tempo estimado:** 15-20 minutos  
> **Prioridade:** Alta (validar antes de usar em produção)  

---

## 📋 CHECKLIST RÁPIDO

```
⏳ 1. Verificar se deploy completou no Railway
⏳ 2. Testar Health Check
⏳ 3. Verificar se migrations rodaram
⏳ 4. Testar Cache Redis (HIT/MISS)
⏳ 5. Testar performance de endpoints
⏳ 6. Verificar logs de erro
⏳ 7. Validar métricas
```

---

## 🚀 FASE 1: VERIFICAR DEPLOY (2 min)

### **1.1 Health Check**
```bash
curl https://alreasense-backend-production.up.railway.app/api/health/
```

**Esperado:**
```json
{
  "status": "healthy",  // ✅ ou "degraded" (RabbitMQ disconnected é normal)
  "database": {"status": "healthy"},
  "redis": {"status": "healthy"}
}
```

**⚠️ Se der erro:** Deploy ainda não completou. Aguarde 2-3 min.

---

### **1.2 Verificar Migrations**
```bash
# Via Railway CLI (se tiver acesso)
railway run python manage.py showmigrations

# OU via logs do Railway
# Procurar por:
# "Running migrations:"
# "  Applying contacts.0003_add_performance_indexes... OK"
# "  Applying campaigns.0010_add_performance_indexes... OK"
# "  Applying chat_messages.0002_add_performance_indexes... OK"
```

**Esperado:** 3 migrations aplicadas ✅

**⚠️ Se migrations não rodaram:**
```bash
# Pode rodar manualmente (se tiver acesso ao banco):
railway run python manage.py migrate
```

---

## 💾 FASE 2: TESTAR CACHE REDIS (5 min)

### **2.1 Produtos - Cache de 24h**

#### **Primeira request (MISS):**
```bash
# Limpar cache primeiro (opcional)
# redis-cli DEL "products:active"

# Request 1: Deve buscar do banco
curl -w "\nTempo: %{time_total}s\n" \
  https://alreasense-backend-production.up.railway.app/api/billing/products/ \
  -H "Authorization: Bearer SEU_TOKEN"
```

**Esperado:**
- Status: 200 OK
- Tempo: ~200-500ms (primeira vez, busca do banco)
- Response: Lista de produtos

#### **Segunda request (HIT):**
```bash
# Request 2: Deve vir do cache
curl -w "\nTempo: %{time_total}s\n" \
  https://alreasense-backend-production.up.railway.app/api/billing/products/ \
  -H "Authorization: Bearer SEU_TOKEN"
```

**Esperado:**
- Status: 200 OK
- Tempo: ~50-100ms ⚡ (muito mais rápido!)
- Response: Mesma lista (do cache)

**✅ SUCESSO SE:** Segunda request for 50-80% mais rápida!

---

### **2.2 Planos - Cache de 12h**

```bash
# Request 1 (MISS)
curl -w "\nTempo: %{time_total}s\n" \
  https://alreasense-backend-production.up.railway.app/api/billing/plans/ \
  -H "Authorization: Bearer SEU_TOKEN"

# Request 2 (HIT - imediata)
curl -w "\nTempo: %{time_total}s\n" \
  https://alreasense-backend-production.up.railway.app/api/billing/plans/ \
  -H "Authorization: Bearer SEU_TOKEN"
```

**Esperado:** Mesma melhoria (50-80% mais rápido)

---

### **2.3 TenantProducts - Cache de 5min**

```bash
# Request 1 (MISS)
curl -w "\nTempo: %{time_total}s\n" \
  https://alreasense-backend-production.up.railway.app/api/billing/tenant-products/ \
  -H "Authorization: Bearer SEU_TOKEN"

# Request 2 (HIT)
curl -w "\nTempo: %{time_total}s\n" \
  https://alreasense-backend-production.up.railway.app/api/billing/tenant-products/ \
  -H "Authorization: Bearer SEU_TOKEN"
```

**Esperado:** Mais rápido na 2ª request

---

## 🏎️ FASE 3: TESTAR PERFORMANCE DE ENDPOINTS (5 min)

### **3.1 TenantViewSet.list() - Esperado < 300ms**

```bash
curl -w "\nTempo total: %{time_total}s\n" \
  https://alreasense-backend-production.up.railway.app/api/tenancy/tenants/ \
  -H "Authorization: Bearer SEU_TOKEN"
```

**ANTES:** ~1.5s (com 200+ queries)  
**DEPOIS:** ~150-300ms (com 3 queries) ✅

**✅ SUCESSO SE:** < 500ms

---

### **3.2 TenantViewSet.metrics() - Esperado < 200ms**

```bash
# Pegar ID de um tenant primeiro:
TENANT_ID="seu-tenant-id-aqui"

curl -w "\nTempo total: %{time_total}s\n" \
  https://alreasense-backend-production.up.railway.app/api/tenancy/tenants/${TENANT_ID}/metrics/ \
  -H "Authorization: Bearer SEU_TOKEN"
```

**ANTES:** ~800ms (com 12+ queries)  
**DEPOIS:** ~100-200ms (com 3 queries) ✅

**✅ SUCESSO SE:** < 300ms

---

### **3.3 ContactViewSet.list() - Esperado < 200ms**

```bash
curl -w "\nTempo total: %{time_total}s\n" \
  https://alreasense-backend-production.up.railway.app/api/contacts/contacts/ \
  -H "Authorization: Bearer SEU_TOKEN"
```

**ANTES:** ~200-300ms  
**DEPOIS:** ~50-150ms (com índices) ✅

**✅ SUCESSO SE:** < 200ms

---

### **3.4 CampaignViewSet.list() - Esperado < 200ms**

```bash
curl -w "\nTempo total: %{time_total}s\n" \
  https://alreasense-backend-production.up.railway.app/api/campaigns/campaigns/ \
  -H "Authorization: Bearer SEU_TOKEN"
```

**ANTES:** ~200-400ms  
**DEPOIS:** ~50-150ms (com índices) ✅

**✅ SUCESSO SE:** < 250ms

---

## 🔍 FASE 4: VERIFICAR ÍNDICES NO BANCO (3 min)

### **4.1 Conectar no PostgreSQL**

```bash
# Via Railway CLI
railway connect postgres

# OU usar credentials do Railway Dashboard
```

### **4.2 Verificar Índices Criados**

```sql
-- Índices de Contact
SELECT indexname, tablename 
FROM pg_indexes 
WHERE tablename = 'contacts_contact' 
  AND indexname LIKE 'idx_%'
ORDER BY indexname;

-- Deve retornar 5 índices:
-- idx_contact_tenant_active
-- idx_contact_tenant_created
-- idx_contact_tenant_email
-- idx_contact_tenant_lifecycle
-- idx_contact_tenant_phone
```

```sql
-- Índices de Campaign
SELECT indexname, tablename 
FROM pg_indexes 
WHERE tablename = 'campaigns_campaign' 
  AND indexname LIKE 'idx_%'
ORDER BY indexname;

-- Deve retornar 2 índices:
-- idx_campaign_tenant_created
-- idx_campaign_tenant_status
```

```sql
-- Índices de CampaignContact
SELECT indexname, tablename 
FROM pg_indexes 
WHERE tablename = 'campaigns_campaigncontact' 
  AND indexname LIKE 'idx_%'
ORDER BY indexname;

-- Deve retornar 2 índices:
-- idx_campaign_contact_campaign_sent
-- idx_campaign_contact_campaign_status
```

```sql
-- Índices de Message
SELECT indexname, tablename 
FROM pg_indexes 
WHERE tablename = 'chat_messages_message' 
  AND indexname LIKE 'idx_%'
ORDER BY indexname;

-- Deve retornar 3 índices:
-- idx_message_tenant_created
-- idx_message_tenant_satisfaction
-- idx_message_tenant_sentiment
```

**✅ TOTAL ESPERADO:** 12 índices

---

## 📊 FASE 5: TESTE DE CARGA (Opcional - 5 min)

### **5.1 Teste de Stress (Apache Bench)**

```bash
# Instalar Apache Bench (se necessário)
# Windows: via chocolatey: choco install apachebench
# Mac: brew install apache-bench
# Linux: apt-get install apache2-utils

# Teste: 100 requests, 10 concorrentes
ab -n 100 -c 10 \
  -H "Authorization: Bearer SEU_TOKEN" \
  https://alreasense-backend-production.up.railway.app/api/billing/products/
```

**Métricas esperadas:**
```
Requests per second: > 50 req/s ✅
Time per request: < 200ms ✅
Failed requests: 0 ✅
```

---

## 🐛 FASE 6: VERIFICAR LOGS DE ERRO (2 min)

### **6.1 Logs do Railway**

```bash
# Via CLI
railway logs --tail 50

# OU no Dashboard: railway.app > seu projeto > Logs
```

**Procurar por:**
```
✅ "Running migrations" - Migrations rodaram
✅ "Applied 3 migrations" - Sucesso
❌ "Error" - Problemas
❌ "IntegrityError" - Problema nos índices
❌ "CacheMiss" excesso - Cache não está funcionando
```

---

## 📈 FASE 7: MÉTRICAS NO FRONTEND (5 min)

### **7.1 Testar no Dashboard**

1. **Login:** https://alreasense-production.up.railway.app/login
2. **Dashboard:** Navegar pelas páginas
3. **Observar:**
   - Tempo de carregamento das páginas
   - Produtos/Planos devem carregar instantaneamente (2ª vez)
   - Métricas devem aparecer rápido

### **7.2 DevTools do Chrome**

1. Abrir **F12** (DevTools)
2. **Network Tab**
3. Recarregar página
4. Procurar requisições:
   - `/api/billing/products/` - **< 100ms** (cache)
   - `/api/billing/plans/` - **< 100ms** (cache)
   - `/api/tenancy/tenants/` - **< 300ms**
   - `/api/tenancy/tenants/{id}/metrics/` - **< 200ms**

**✅ SUCESSO SE:** Todas < 300ms (exceto 1ª request de cada)

---

## ⚠️ PROBLEMAS COMUNS E SOLUÇÕES

### **Problema 1: Migrations não rodaram**

```bash
# Solução: Rodar manualmente
railway run python manage.py migrate contacts
railway run python manage.py migrate campaigns
railway run python manage.py migrate chat_messages
```

---

### **Problema 2: Cache não está funcionando**

```bash
# Verificar Redis
railway run redis-cli PING
# Esperado: PONG

# Limpar cache e tentar novamente
railway run redis-cli FLUSHDB
```

---

### **Problema 3: Performance ainda lenta**

**Verificar:**
1. Índices foram criados? (Fase 4)
2. Cache está ativo? (Fase 2)
3. Migrations rodaram? (Fase 1.2)

**Logs para analisar:**
```bash
railway logs --tail 100 | grep -i "error\|warning\|slow"
```

---

### **Problema 4: Erro 500 em algum endpoint**

```bash
# Ver logs detalhados
railway logs --tail 50

# Procurar por:
# - Erro de import
# - Erro de cache
# - Erro de query
```

---

## 🎯 CRITÉRIOS DE SUCESSO

### **✅ TUDO OK SE:**

```
1. ✅ Health check retorna "healthy" ou "degraded" (RabbitMQ ok)
2. ✅ 3 migrations aplicadas (contacts, campaigns, chat_messages)
3. ✅ 12 índices criados no banco
4. ✅ Cache funciona (2ª request 50-80% mais rápida)
5. ✅ Endpoints < 300ms
6. ✅ Zero erros nos logs
7. ✅ Frontend carrega rápido
```

---

## 🚨 ROLLBACK (Se der muito problema)

```bash
# 1. Reverter commit
git revert c2b4ac6

# 2. Push
git push origin main

# 3. Railway vai deployar versão anterior
```

**MAS:** Improvável precisar! As otimizações são seguras ✅

---

## 📊 MÉTRICAS ESPERADAS (RESUMO)

| Endpoint | ANTES | DEPOIS | META |
|----------|-------|--------|------|
| **Health** | N/A | N/A | < 100ms |
| **Products** (cache) | 300ms | 50ms | < 100ms |
| **Plans** (cache) | 250ms | 50ms | < 100ms |
| **Tenants.list()** | 1500ms | 200ms | < 300ms |
| **Tenants.metrics()** | 800ms | 150ms | < 200ms |
| **Contacts.list()** | 250ms | 100ms | < 200ms |
| **Campaigns.list()** | 300ms | 120ms | < 250ms |

---

## 🎊 RESULTADO ESPERADO

```
Performance Score: ⭐⭐⭐⭐⭐ (5/5)

✅ Cache Redis: 99% hit rate
✅ Queries reduzidas: 95%
✅ Tempo de resposta: 87% melhoria
✅ Índices ativos: 12/12
✅ Zero N+1 queries
✅ Sistema pronto para escalar!
```

---

## 📞 SUPORTE

Se algo der errado:
1. Verificar logs: `railway logs`
2. Testar localmente primeiro
3. Fazer rollback se crítico

---

**Bora testar! Siga as fases na ordem e me avise os resultados!** 🚀

_Gerado em: 21/10/2025 | Tempo estimado: 15-20 min_

