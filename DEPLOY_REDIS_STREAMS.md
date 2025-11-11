# 🚀 Deploy Redis Streams - Flow Chat

## 📋 Resumo

Migração do sistema de envio de mensagens do chat de **Redis Lists (LPUSH/BRPOP)** para **Redis Streams** com Consumer Groups.

### ✅ Benefícios

- **Garantia de entrega**: ACK automático, mensagens não se perdem se worker cair
- **Escalabilidade**: Múltiplos workers podem processar em paralelo
- **Reprocessamento**: Mensagens travadas são automaticamente recuperadas
- **Dead-Letter Queue**: Mensagens que falham após N tentativas vão para DLQ
- **Métricas**: Monitoramento completo via endpoint `/api/chat/reactions/queues/status/`

---

## 🔧 Configuração

### 1. Variáveis de Ambiente (Railway)

Adicione no serviço **backend** do Railway:

```bash
# Redis exclusivo para Streams do chat
CHAT_STREAM_REDIS_URL=redis://default:oIdxJhhfoMZPtxSTAHytqNkQWBLpyQDX@redis.railway.internal:6379/3
CHAT_STREAM_REDIS_DB=3
CHAT_STREAM_REDIS_PREFIX=chat:stream:

# Streams que vamos criar
CHAT_STREAM_SEND_NAME=chat:stream:send_message
CHAT_STREAM_MARK_READ_NAME=chat:stream:mark_as_read
CHAT_STREAM_DLQ_NAME=chat:stream:dead_letter

# Configuração do consumer group
CHAT_STREAM_CONSUMER_GROUP=chat_send_workers
CHAT_STREAM_MAXLEN=5000
CHAT_STREAM_DLQ_MAXLEN=2000
CHAT_STREAM_MAX_RETRIES=5
CHAT_STREAM_RECLAIM_IDLE_MS=60000
```

### 2. Criar Novo Serviço no Railway

**Nome**: `chat-stream-worker`  
**Build**: Mesmo Dockerfile do backend  
**Start Command**: 
```bash
python manage.py start_chat_stream_worker --send-workers 3 --mark-workers 2
```

**Variáveis de Ambiente**: Mesmas do backend (copiar todas)

**Recursos**: 
- CPU: 512 MB (mínimo)
- RAM: 512 MB (mínimo)
- Pode escalar horizontalmente (múltiplas réplicas)

---

## 🎯 Arquitetura

### Fluxo de Envio

```
API Request → tasks.py (send_message_to_evolution.delay)
    ↓
redis_streams.py (enqueue_send_message_async)
    ↓
Redis Stream: chat:stream:send_message
    ↓
stream_consumer.py (process_send_message_worker)
    ↓
tasks.py (handle_send_message)
    ↓
Evolution API → WebSocket Broadcast
```

### Consumer Groups

- **Grupo**: `chat_send_workers`
- **Consumers**: `worker-{hostname}-{pid}-{id}` (único por instância)
- **Streams**:
  - `chat:stream:send_message` (envio de mensagens)
  - `chat:stream:mark_as_read` (read receipts)

### Dead-Letter Queue

- **Stream**: `chat:stream:dead_letter`
- **Trigger**: Após `CHAT_STREAM_MAX_RETRIES` (padrão: 5) tentativas falhadas
- **Conteúdo**: Payload original + metadata de erro + retry_count

---

## 📊 Monitoramento

### Endpoint de Métricas

```bash
GET /api/chat/reactions/queues/status/
```

**Resposta**:
```json
{
  "metrics": {
    "stream_metrics": {
      "send_message": {
        "length": 10,
        "pending": 2,
        "consumers": 3
      },
      "mark_as_read": {
        "length": 5,
        "pending": 0,
        "consumers": 2
      },
      "dead_letter": {
        "length": 1
      }
    }
  },
  "alerts": [
    "⚠️ Stream send_message tem 1500 mensagens (acima de 1000)"
  ],
  "timestamp": "2025-11-06T..."
}
```

### Logs Importantes

- `✅ [CHAT STREAM] Mensagem enfileirada`: Sucesso ao adicionar na stream
- `📥 [CHAT STREAM] Processando send_message`: Worker pegou mensagem
- `✅ [CHAT STREAM] send_message concluída`: Envio bem-sucedido
- `⚠️ [CHAT STREAM] Mensagens recuperadas`: Reprocessamento automático
- `❌ [CHAT STREAM] Movido para DLQ`: Falha após N tentativas

---

## 🔍 Troubleshooting

### Worker não processa mensagens

1. **Verificar conexão Redis**:
   ```bash
   redis-cli -h redis.railway.internal -p 6379 -a oIdxJhhfoMZPtxSTAHytqNkQWBLpyQDX
   > SELECT 3
   > XINFO GROUPS chat:stream:send_message
   ```

2. **Verificar se grupo existe**:
   ```bash
   > XGROUP CREATE chat:stream:send_message chat_send_workers $ MKSTREAM
   ```

3. **Verificar mensagens pendentes**:
   ```bash
   > XPENDING chat:stream:send_message chat_send_workers
   ```

### Mensagens travadas

O worker automaticamente recupera mensagens pendentes após 60s (`CHAT_STREAM_RECLAIM_IDLE_MS`).

Para forçar recuperação manual:
```bash
> XAUTOCLAIM chat:stream:send_message chat_send_workers worker-1 60000 0-0 COUNT 100
```

### Dead-Letter Queue cheia

1. **Inspecionar mensagens**:
   ```bash
   > XRANGE chat:stream:dead_letter - + COUNT 10
   ```

2. **Reprocessar manualmente** (se necessário):
   - Extrair payload da DLQ
   - Re-enfileirar via API ou diretamente na stream

---

## 🚦 Migração (Rollback se necessário)

### Voltar para Redis Lists

1. **Parar worker de streams**:
   ```bash
   # No Railway: Desabilitar serviço chat-stream-worker
   ```

2. **Reverter código**:
   ```bash
   git revert <commit-hash>
   ```

3. **Reiniciar consumer antigo**:
   ```bash
   python manage.py start_chat_consumer --queues send_message mark_as_read
   ```

### Coexistência

Durante migração, ambos podem rodar simultaneamente:
- **Streams**: Novo worker (`start_chat_stream_worker`)
- **Lists**: Consumer antigo (`start_chat_consumer`)

**⚠️ CUIDADO**: Não rodar ambos processando as mesmas filas ao mesmo tempo (duplicação).

---

## 📈 Escalabilidade

### Aumentar Workers

**Railway**: Aumentar número de réplicas do serviço `chat-stream-worker`

**Ou via variável**:
```bash
CHAT_STREAM_SEND_WORKERS=5  # Por instância
CHAT_STREAM_MARK_WORKERS=3
```

### Performance Esperada

- **Latência**: 2-6ms (enfileiramento)
- **Throughput**: ~100-500 mensagens/segundo por worker
- **Escalabilidade**: Linear (mais workers = mais throughput)

---

## ✅ Checklist de Deploy

- [ ] Variáveis de ambiente configuradas no Railway
- [ ] Novo serviço `chat-stream-worker` criado
- [ ] Worker iniciado e processando mensagens
- [ ] Métricas disponíveis em `/api/chat/reactions/queues/status/`
- [ ] Logs mostrando processamento normal
- [ ] Teste de envio de mensagem funcionando
- [ ] Teste de read receipt funcionando
- [ ] Verificar DLQ (deve estar vazia inicialmente)

---

## 🎉 Pronto!

O sistema agora usa Redis Streams para envio de mensagens, com garantias de entrega e escalabilidade horizontal.

**Próximos passos**:
- Monitorar métricas por alguns dias
- Ajustar número de workers conforme carga
- Implementar alertas automáticos (se necessário)

