# ✅ CHECKLIST DE DEPLOY - SISTEMA DE MÍDIA

> **Data:** 18 de Novembro de 2025 - 10:40 BRT  
> **Versão:** 2025.11.18 - Fix webhooks e campanhas  
> **Deploy:** Railway Automatic  
> **Status:** Testando detecção automática após interrupção Cloudflare  

## 📝 Últimas Mudanças (18/11/2025)

- ✅ Corrigido UnboundLocalError do logger nos webhooks de campanha
- ✅ Adicionado recálculo automático de stats de campanha no serializer
- ✅ Corrigida exibição de logs de delivered e read no modal
- ✅ Melhorada exibição de contadores de campanha no frontend
- ✅ Webhooks agora processam corretamente eventos de entrega e leitura

---

## 📋 PRÉ-DEPLOY

### Código
- ✅ Todos os commits realizados
- ✅ Push para `origin/main` concluído
- ✅ Branch atualizada (8d5e04f)

### Dependências
- ✅ `boto3==1.34.0` (S3/MinIO)
- ✅ `Pillow==10.1.0` (Processamento de imagens)
- ✅ `httpx==0.25.2` (HTTP client async)
- ✅ `aio-pika==9.3.1` (RabbitMQ)

### Arquivos Novos
- ✅ `backend/apps/chat/utils/s3.py`
- ✅ `backend/apps/chat/utils/image_processing.py`
- ✅ `backend/apps/chat/media_tasks.py`
- ✅ `frontend/src/components/MediaUpload.tsx`
- ✅ `frontend/src/components/MediaPreview.tsx`

---

## 🔧 CONFIGURAÇÃO RAILWAY

### Variáveis de Ambiente Necessárias

```bash
# S3/MinIO (já configuradas)
S3_BUCKET=flow-attachments
S3_ENDPOINT_URL=https://bucket-production-8fb1.up.railway.app
S3_ACCESS_KEY=u2gh8aomMEdqPFW1JIlTn7VcCUhRCobL
S3_SECRET_KEY=zSMwLiOH1fURqSNX8zMtMYKBjrScDQYynCW2TbI2UuXM7Bti
S3_REGION=us-east-1

# Redis (já configurado)
REDIS_URL=redis://...

# RabbitMQ (já configurado)
RABBITMQ_PRIVATE_URL=amqp://...

# Django (já configurado)
DATABASE_URL=postgresql://...
SECRET_KEY=...
DEBUG=False
```

**Status:** ✅ Todas as variáveis já estão configuradas no Railway

---

## 🚀 DEPLOY AUTOMÁTICO

### Processo Railway

```
1. ✅ Git Push detectado
2. ⏳ Build iniciado (estimado: 2-3 min)
   ├─ Instalando dependências (pip install)
   ├─ Rodando migrações (manage.py migrate)
   ├─ Coletando static files
   └─ Build do frontend (npm run build)
3. ⏳ Deploy em andamento
   ├─ Backend (Daphne)
   ├─ WebSocket (Channels + Redis)
   └─ RabbitMQ Consumers (aio-pika)
4. ⏳ Health Check
5. ✅ Deploy Completo
```

### Timeline Estimado
```
00:00 - Push detectado
00:30 - Build iniciado
02:00 - Build concluído
02:30 - Deploy iniciado
03:00 - Deploy completo
03:30 - Health check OK
```

---

## 🧪 TESTES PÓS-DEPLOY

### 1. Backend Health Check

```bash
# Teste básico
curl https://alreasense-backend-production.up.railway.app/api/health/

# Resposta esperada:
{"status": "ok"}
```

### 2. Media Proxy

```bash
# Teste proxy de mídia
curl "https://alreasense-backend-production.up.railway.app/api/chat/media-proxy/?url=https://via.placeholder.com/150"

# Deve retornar imagem com headers:
# X-Cache: MISS (primeira vez) ou HIT (cache)
```

### 3. Upload Endpoint

```bash
# Teste upload (precisa de auth)
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "file=@test.jpg" \
  https://alreasense-backend-production.up.railway.app/api/chat/upload-media/

# Resposta esperada:
{
  "success": true,
  "file_url": "https://...",
  "thumbnail_url": "https://...",
  "file_type": "image"
}
```

### 4. S3 Connection

```bash
# Verificar se consegue conectar no MinIO
# (interno - ver logs do Railway)
```

### 5. WebSocket

```javascript
// Teste WebSocket (frontend)
const ws = new WebSocket('wss://alreasense-backend-production.up.railway.app/ws/tenant/<tenant_id>/')
ws.onopen = () => console.log('✅ WebSocket conectado')
ws.onerror = (e) => console.error('❌ WebSocket erro:', e)
```

---

## 📊 MONITORAMENTO

### Logs a Verificar

```bash
# Railway Logs
railway logs --tail

# Procurar por:
✅ [S3] Upload realizado
✅ [MEDIA PROXY] Download concluído
✅ [RABBITMQ] Task enfileirada
✅ [IMG] Processamento completo
❌ Qualquer erro de S3/MinIO
```

### Métricas Importantes

```
- Tempo de resposta do proxy: < 1s (cache) / < 3s (download)
- Taxa de sucesso de upload: > 95%
- Tamanho médio de thumbnail: < 50KB
- Cache hit rate: > 70% (após alguns dias)
```

---

## ⚠️ PROBLEMAS COMUNS

### 1. MinIO/S3 Não Conecta

**Sintoma:** Erro "Could not connect to endpoint"

**Solução:**
```bash
# Verificar variáveis de ambiente no Railway
railway variables

# Testar conexão manual
python -c "
import boto3
s3 = boto3.client('s3', endpoint_url='...', ...)
print(s3.list_buckets())
"
```

### 2. Pillow Não Instalou

**Sintoma:** "ModuleNotFoundError: No module named 'PIL'"

**Solução:**
```bash
# Verificar requirements.txt
cat backend/requirements.txt | grep Pillow

# Se necessário, adicionar build dependencies
# Railway normalmente já tem libjpeg, zlib, etc
```

### 3. Cache Redis Não Funciona

**Sintoma:** Sempre retorna X-Cache: MISS

**Solução:**
```python
# Testar cache manualmente
from django.core.cache import cache
cache.set('test', 'value', 60)
print(cache.get('test'))  # Deve retornar 'value'
```

### 4. RabbitMQ Consumer Não Inicia

**Sintoma:** Tasks não são processadas

**Solução:**
```bash
# Verificar logs do asgi.py
# Procurar por:
# "🚀 [RABBITMQ] RabbitMQ Consumer (aio-pika) inicializado"

# Se não aparecer, verificar RABBITMQ_PRIVATE_URL
```

---

## 🎯 CRITÉRIOS DE SUCESSO

### Deploy Considerado Bem-Sucedido Se:

- ✅ Backend responde em `/api/health/`
- ✅ Frontend carrega sem erros 404
- ✅ WebSocket conecta
- ✅ Proxy de mídia retorna imagens
- ✅ Upload de arquivo funciona
- ✅ S3 recebe arquivos
- ✅ Cache Redis funciona
- ✅ RabbitMQ processa tasks

### Tempo Esperado Até Produção: **5-10 minutos**

---

## 📞 ROLLBACK (Se Necessário)

```bash
# Reverter para commit anterior
git revert 8d5e04f
git push origin main

# Ou voltar para versão específica
git reset --hard b98ea2d
git push origin main --force  # ⚠️ Cuidado!

# Railway fará deploy automático da versão antiga
```

---

## ✅ PÓS-DEPLOY

### Tarefas Imediatas

1. ⏳ **Testar upload de imagem** (via frontend)
2. ⏳ **Verificar foto de perfil** (deve carregar via proxy)
3. ⏳ **Enviar mensagem com anexo** (testar fluxo completo)
4. ⏳ **Monitorar logs** (primeiros 30 min)
5. ⏳ **Verificar métricas Railway** (CPU, RAM, latência)

### Tarefas nas Próximas 24h

1. ⏳ **Monitorar erros** (Sentry, logs)
2. ⏳ **Verificar cache hit rate** (Redis)
3. ⏳ **Checar uso de storage S3** (MinIO dashboard)
4. ⏳ **Testar com arquivos grandes** (10MB+)
5. ⏳ **Validar performance** (tempo de resposta)

### Tarefas na Primeira Semana

1. ⏳ **Implementar melhorias** (validação de extensões, retry)
2. ⏳ **Adicionar métricas** (dashboard de uploads)
3. ⏳ **Otimizar cache** (ajustar TTL se necessário)
4. ⏳ **Documentar edge cases** (encontrados em produção)
5. ⏳ **Coletar feedback** (usuários)

---

## 📈 MÉTRICAS DE SUCESSO (Primeira Semana)

```
Meta:
- Uptime: > 99.5%
- Taxa de sucesso upload: > 95%
- Cache hit rate: > 60%
- Tempo resposta proxy: < 2s média
- 0 bugs críticos
- 0 downtime não planejado
```

---

## 🎊 CONCLUSÃO

**Deploy Status:** ⏳ EM ANDAMENTO

**Próximos Passos:**
1. Aguardar build Railway (~3 min)
2. Verificar logs do deploy
3. Executar testes pós-deploy
4. Monitorar por 30 minutos
5. Declarar deploy bem-sucedido ✅

---

**Última atualização:** 20 de Outubro de 2025  
**Responsável:** Time de Desenvolvimento ALREA Sense

