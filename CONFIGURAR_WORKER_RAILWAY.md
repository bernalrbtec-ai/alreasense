# ⚙️ Configurar Worker no Railway

## ❌ Problema Atual

O worker está tentando conectar ao PostgreSQL em `localhost:5432`, mas não consegue porque:

1. **Variáveis de ambiente não configuradas** no serviço `chat-stream-worker`
2. O Django precisa de acesso ao banco para inicializar (importa models, tasks, etc)

## ✅ Solução

### 1. Copiar TODAS as variáveis de ambiente do backend

No Railway, no serviço `chat-stream-worker`, você precisa copiar **TODAS** as variáveis do serviço `backend`:

#### Variáveis Obrigatórias:

```bash
# Database
DATABASE_URL=postgresql://...

# Redis (geral)
REDIS_URL=redis://...
REDISHOST=redis.railway.internal
REDISPASSWORD=...
REDISPORT=6379
REDISUSER=default

# Redis Streams (novas)
CHAT_STREAM_REDIS_URL=redis://default:...@redis.railway.internal:6379/3
CHAT_STREAM_REDIS_DB=3
CHAT_STREAM_REDIS_PREFIX=chat:stream:
CHAT_STREAM_SEND_NAME=chat:stream:send_message
CHAT_STREAM_MARK_READ_NAME=chat:stream:mark_as_read
CHAT_STREAM_DLQ_NAME=chat:stream:dead_letter
CHAT_STREAM_CONSUMER_GROUP=chat_send_workers
CHAT_STREAM_MAXLEN=5000
CHAT_STREAM_DLQ_MAXLEN=2000
CHAT_STREAM_MAX_RETRIES=5
CHAT_STREAM_RECLAIM_IDLE_MS=60000

# Django
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=...
CORS_ALLOWED_ORIGINS=...

# Evolution API
EVO_BASE_URL=...
EVO_API_KEY=...

# RabbitMQ (se necessário)
RABBITMQ_URL=...

# Outras variáveis que o backend usa
```

### 2. Como copiar no Railway

**Opção A: Manual (mais rápido)**
1. Vá no serviço `backend` → **Variables**
2. Copie todas as variáveis
3. Vá no serviço `chat-stream-worker` → **Variables**
4. Cole todas as variáveis

**Opção B: Via Railway CLI**
```bash
# Exportar do backend
railway variables --service backend > backend_vars.txt

# Importar no worker (ajustar service name)
railway variables --service chat-stream-worker < backend_vars.txt
```

### 3. Verificar Start Command

Certifique-se de que o Start Command está configurado:

```
python manage.py start_chat_stream_worker --send-workers 3 --mark-workers 2
```

### 4. Verificar Build

O worker usa o mesmo Dockerfile do backend, então o build deve funcionar normalmente.

---

## 🔍 Verificação

Após configurar as variáveis, verifique os logs do worker:

**Logs esperados:**
```
✅ [SETTINGS] All configurations loaded successfully!
🚀 [CHAT STREAM] Iniciando workers Redis Streams...
📥 [CHAT STREAM] Worker send_message-1 iniciado
📥 [CHAT STREAM] Worker send_message-2 iniciado
📥 [CHAT STREAM] Worker send_message-3 iniciado
📥 [CHAT STREAM] Worker mark_as_read-1 iniciado
📥 [CHAT STREAM] Worker mark_as_read-2 iniciado
✅ [CHAT STREAM] Todos os workers iniciados!
```

**Se ainda der erro de conexão:**
- Verifique se `DATABASE_URL` está correto
- Verifique se o PostgreSQL está acessível do worker (mesma rede Railway)
- Verifique se não há firewall bloqueando

---

## ⚠️ Importante

O worker **NÃO precisa** de:
- ❌ Porta exposta (não tem servidor HTTP)
- ❌ Healthcheck HTTP (processo roda em loop)
- ❌ Muitos recursos (512MB RAM, 1 vCPU é suficiente)

O worker **PRECISA** de:
- ✅ Todas as variáveis de ambiente do backend
- ✅ Acesso ao mesmo PostgreSQL
- ✅ Acesso ao mesmo Redis (DB 3 para streams)
- ✅ Start Command configurado

---

## 🚀 Pronto!

Após copiar as variáveis, o worker deve iniciar normalmente e começar a processar mensagens das streams.

