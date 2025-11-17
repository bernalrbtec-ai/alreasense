# 🚀 PLANO DE MIGRAÇÃO: RabbitMQ → Redis para Chat

**Data:** 22 de outubro de 2025  
**Objetivo:** Migrar filas do chat de RabbitMQ para Redis (10x mais rápido)  
**Dados atuais:** Irrelevantes (não precisa preservar)  
**Status:** Pronto para implementar

---

## 📊 **ANÁLISE DO ESTADO ATUAL**

### **Filas RabbitMQ Atuais:**

| Fila | Uso | Latência Crítica | Migrar? |
|------|-----|------------------|---------|
| `chat_send_message` | Enviar mensagem via Evolution API | ✅ SIM | ✅ **SIM** |
| `chat_fetch_profile_pic` | Buscar foto de perfil | ✅ SIM | ✅ **SIM** |
| `chat_fetch_group_info` | Buscar info de grupo | ✅ SIM | ✅ **SIM** |
| `chat_process_incoming_media` | Processar mídia recebida | ❌ NÃO | ❌ **MANTER RabbitMQ** |

### **Estrutura Atual:**

```
RabbitMQ
├── chat_send_message (migrar → Redis)
├── chat_fetch_profile_pic (migrar → Redis)
├── chat_fetch_group_info (migrar → Redis)
└── chat_process_incoming_media (manter RabbitMQ)
```

---

## 🎯 **ESTRUTURA NOVA (Redis)**

### **Redis Database 2 (Chat Queues):**

```
Redis Database 2
├── chat:queue:send_message (LPUSH/BRPOP)
├── chat:queue:fetch_profile_pic (LPUSH/BRPOP)
└── chat:queue:fetch_group_info (LPUSH/BRPOP)
```

### **Redis Database 0 (Cache):**
- Django Cache (já em uso)
- Webhook Cache (já em uso)

### **Redis Database 1 (Channels):**
- Channels WebSocket (já em uso)

---

## 📋 **PASSO A PASSO DA MIGRAÇÃO**

### **FASE 1: Preparação (30 min)**

#### **1.1. Criar módulo Redis Queue**

```python
# backend/apps/chat/redis_queue.py
```

**Arquivos:**
- ✅ `backend/apps/chat/redis_queue.py` (NOVO)
- ✅ `backend/apps/chat/redis_consumer.py` (NOVO)

#### **1.2. Configurar Redis Database 2**

```python
# backend/apps/chat/redis_queue.py

import redis
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Prefixo para filas
QUEUE_PREFIX = "chat:queue:"

# Nomes das filas Redis
REDIS_QUEUE_SEND_MESSAGE = f"{QUEUE_PREFIX}send_message"
REDIS_QUEUE_FETCH_PROFILE_PIC = f"{QUEUE_PREFIX}fetch_profile_pic"
REDIS_QUEUE_FETCH_GROUP_INFO = f"{QUEUE_PREFIX}fetch_group_info"

def get_chat_redis_client():
    """Get Redis client for chat queues (Database 2)"""
    redis_url = settings.REDIS_URL
    
    if not redis_url or redis_url == '':
        logger.warning("⚠️ Redis URL not configured")
        return None
    
    # Usar Database 2 para filas do chat
    # redis://host:port/2
    chat_redis_url = redis_url.replace('/0', '/2')
    
    return redis.Redis.from_url(
        chat_redis_url,
        decode_responses=True,
        max_connections=50,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True
    )

def enqueue_message(queue_name: str, payload: dict):
    """
    Enfileira mensagem no Redis (LPUSH).
    
    Args:
        queue_name: Nome da fila (ex: REDIS_QUEUE_SEND_MESSAGE)
        payload: Dados da mensagem
    
    Returns:
        int: Número de mensagens na fila após adicionar
    """
    try:
        client = get_chat_redis_client()
        if client is None:
            logger.error("❌ [REDIS] Redis client não disponível")
            raise Exception("Redis client não disponível")
        
        # Enfileirar mensagem (LPUSH)
        message = json.dumps(payload)
        queue_length = client.lpush(queue_name, message)
        
        logger.info(f"✅ [REDIS] Mensagem enfileirada: {queue_name} (fila: {queue_length} msgs)")
        return queue_length
        
    except Exception as e:
        logger.error(f"❌ [REDIS] Erro ao enfileirar mensagem: {e}", exc_info=True)
        raise

def dequeue_message(queue_name: str, timeout: int = 5):
    """
    Desenfileira mensagem do Redis (BRPOP).
    
    Args:
        queue_name: Nome da fila
        timeout: Timeout em segundos (0 = sem timeout)
    
    Returns:
        dict: Dados da mensagem ou None se timeout
    """
    try:
        client = get_chat_redis_client()
        if client is None:
            logger.error("❌ [REDIS] Redis client não disponível")
            return None
        
        # Desenfileirar mensagem (BRPOP)
        result = client.brpop(queue_name, timeout=timeout)
        
        if result is None:
            return None
        
        # result = (queue_name, message_json)
        _, message_json = result
        payload = json.loads(message_json)
        
        logger.debug(f"✅ [REDIS] Mensagem desenfileirada: {queue_name}")
        return payload
        
    except Exception as e:
        logger.error(f"❌ [REDIS] Erro ao desenfileirar mensagem: {e}", exc_info=True)
        return None
```

---

### **FASE 2: Implementação (2-3 horas)**

#### **2.1. Criar Producers Redis**

```python
# backend/apps/chat/tasks.py (ATUALIZAR)

# ✅ NOVO: Producers Redis
from apps.chat.redis_queue import (
    enqueue_message,
    REDIS_QUEUE_SEND_MESSAGE,
    REDIS_QUEUE_FETCH_PROFILE_PIC,
    REDIS_QUEUE_FETCH_GROUP_INFO
)

class send_message_to_evolution:
    """Producer: Envia mensagem para Evolution API (Redis)."""
    
    @staticmethod
    def delay(message_id: str):
        """Enfileira mensagem para envio (Redis)."""
        enqueue_message(REDIS_QUEUE_SEND_MESSAGE, {'message_id': message_id})

class fetch_profile_pic:
    """Producer: Busca foto de perfil via Evolution API (Redis)."""
    
    @staticmethod
    def delay(conversation_id: str, phone: str):
        """Enfileira busca de foto de perfil (Redis)."""
        enqueue_message(REDIS_QUEUE_FETCH_PROFILE_PIC, {
            'conversation_id': conversation_id,
            'phone': phone
        })

class fetch_group_info:
    """Producer: Busca info de grupo via Evolution API (Redis)."""
    
    @staticmethod
    def delay(conversation_id: str, group_jid: str, instance_name: str, api_key: str, base_url: str):
        """Enfileira busca de info de grupo (Redis)."""
        enqueue_message(REDIS_QUEUE_FETCH_GROUP_INFO, {
            'conversation_id': conversation_id,
            'group_jid': group_jid,
            'instance_name': instance_name,
            'api_key': api_key,
            'base_url': base_url
        })

# ❌ REMOVER: Producers RabbitMQ antigos (substituídos acima)
```

#### **2.2. Criar Consumer Redis**

```python
# backend/apps/chat/redis_consumer.py (NOVO)

import asyncio
import logging
from apps.chat.redis_queue import (
    dequeue_message,
    REDIS_QUEUE_SEND_MESSAGE,
    REDIS_QUEUE_FETCH_PROFILE_PIC,
    REDIS_QUEUE_FETCH_GROUP_INFO
)
from apps.chat.tasks import (
    handle_send_message,
    handle_fetch_profile_pic
)
from apps.chat.media_tasks import handle_fetch_group_info

logger = logging.getLogger(__name__)

async def start_redis_consumers():
    """
    Inicia consumers Redis para processar filas do chat.
    Roda em loop infinito processando mensagens.
    """
    logger.info("🚀 [REDIS CONSUMER] Iniciando consumers Redis do chat...")
    
    async def process_send_message():
        """Processa fila send_message."""
        while True:
            try:
                payload = dequeue_message(REDIS_QUEUE_SEND_MESSAGE, timeout=5)
                
                if payload:
                    logger.info(f"📥 [REDIS CONSUMER] Recebida task send_message: {payload.get('message_id')}")
                    await handle_send_message(payload['message_id'])
                    logger.info(f"✅ [REDIS CONSUMER] send_message concluída: {payload.get('message_id')}")
                
                # Pequeno delay para não sobrecarregar
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ [REDIS CONSUMER] Erro send_message: {e}", exc_info=True)
                await asyncio.sleep(1)  # Delay em caso de erro
    
    async def process_fetch_profile_pic():
        """Processa fila fetch_profile_pic."""
        while True:
            try:
                payload = dequeue_message(REDIS_QUEUE_FETCH_PROFILE_PIC, timeout=5)
                
                if payload:
                    logger.info(f"📥 [REDIS CONSUMER] Recebida task fetch_profile_pic")
                    await handle_fetch_profile_pic(
                        payload['conversation_id'],
                        payload['phone']
                    )
                    logger.info(f"✅ [REDIS CONSUMER] fetch_profile_pic concluída")
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ [REDIS CONSUMER] Erro fetch_profile_pic: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def process_fetch_group_info():
        """Processa fila fetch_group_info."""
        while True:
            try:
                payload = dequeue_message(REDIS_QUEUE_FETCH_GROUP_INFO, timeout=5)
                
                if payload:
                    logger.info(f"📥 [REDIS CONSUMER] Recebida task fetch_group_info")
                    await handle_fetch_group_info(
                        payload['conversation_id'],
                        payload['group_jid'],
                        payload['instance_name'],
                        payload['api_key'],
                        payload['base_url']
                    )
                    logger.info(f"✅ [REDIS CONSUMER] fetch_group_info concluída")
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ [REDIS CONSUMER] Erro fetch_group_info: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    # Executar consumers em paralelo
    logger.info("✅ [REDIS CONSUMER] Consumers iniciados!")
    await asyncio.gather(
        process_send_message(),
        process_fetch_profile_pic(),
        process_fetch_group_info()
    )
```

#### **2.3. Atualizar ASGI para iniciar Consumer Redis**

```python
# backend/alrea_sense/asgi.py (ATUALIZAR)

# ❌ REMOVER: start_flow_chat_consumer (RabbitMQ)
# ✅ ADICIONAR: start_redis_chat_consumer (Redis)

def start_redis_chat_consumer():
    """Inicia o Redis Consumer do chat em thread separada"""
    try:
        import asyncio
        time.sleep(12)  # Espera um pouco mais que o consumer de campanhas
        
        from apps.chat.redis_consumer import start_redis_consumers
        
        print("🚀 [REDIS CHAT] Iniciando Redis Chat Consumer...")
        asyncio.run(start_redis_consumers())
        print("✅ [REDIS CHAT] Consumer pronto para processar mensagens!")
            
    except Exception as e:
        print(f"❌ [REDIS CHAT] Erro ao iniciar Redis Chat Consumer: {e}")

# Iniciar consumers apenas se não estiver em DEBUG (produção)
if not os.environ.get('DEBUG', 'False').lower() == 'true':
    # Consumer de campanhas (RabbitMQ)
    consumer_thread = threading.Thread(target=start_rabbitmq_consumer, daemon=True)
    consumer_thread.start()
    print("🧵 [RABBITMQ] Thread do RabbitMQ Consumer iniciada")
    
    # ❌ REMOVER: Consumer do Flow Chat (RabbitMQ)
    # flow_chat_thread = threading.Thread(target=start_flow_chat_consumer, daemon=True)
    # flow_chat_thread.start()
    # print("🧵 [FLOW CHAT] Thread do Flow Chat Consumer iniciada")
    
    # ✅ ADICIONAR: Consumer do Flow Chat (Redis)
    redis_chat_thread = threading.Thread(target=start_redis_chat_consumer, daemon=True)
    redis_chat_thread.start()
    print("🧵 [REDIS CHAT] Thread do Redis Chat Consumer iniciada")
```

#### **2.4. Atualizar Management Command**

```python
# backend/apps/chat/management/commands/start_chat_consumer.py (ATUALIZAR)

"""
Management command para iniciar o consumer Redis do chat.
Executar: python manage.py start_chat_consumer
"""
import asyncio
from django.core.management.base import BaseCommand
from apps.chat.redis_consumer import start_redis_consumers  # ✅ MUDAR: RabbitMQ → Redis


class Command(BaseCommand):
    """
    Inicia consumers Redis para processar filas do chat.
    Roda em loop infinito processando mensagens.
    """
    
    help = 'Inicia consumers Redis para Flow Chat'  # ✅ MUDAR: RabbitMQ → Redis
    
    def handle(self, *args, **options):
        """Executa consumer."""
        self.stdout.write(self.style.SUCCESS('🚀 Iniciando consumer do Flow Chat (Redis)...'))
        
        try:
            asyncio.run(start_redis_consumers())  # ✅ MUDAR: RabbitMQ → Redis
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n⚠️ Consumer interrompido pelo usuário'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro: {e}'))
```

---

### **FASE 3: Testes (1 hora)**

#### **3.1. Testes Locais**

```python
# backend/apps/chat/tests/test_redis_queue.py (NOVO)

import pytest
from apps.chat.redis_queue import (
    enqueue_message,
    dequeue_message,
    REDIS_QUEUE_SEND_MESSAGE
)

@pytest.mark.django_db
def test_enqueue_dequeue_message():
    """Testa enfileirar e desenfileirar mensagem."""
    # Enfileirar
    payload = {'message_id': 'test-123'}
    queue_length = enqueue_message(REDIS_QUEUE_SEND_MESSAGE, payload)
    assert queue_length > 0
    
    # Desenfileirar
    result = dequeue_message(REDIS_QUEUE_SEND_MESSAGE, timeout=1)
    assert result is not None
    assert result['message_id'] == 'test-123'

@pytest.mark.django_db
def test_send_message_producer():
    """Testa producer send_message_to_evolution."""
    from apps.chat.tasks import send_message_to_evolution
    
    # Enfileirar mensagem
    send_message_to_evolution.delay('test-123')
    
    # Verificar se está na fila
    result = dequeue_message(REDIS_QUEUE_SEND_MESSAGE, timeout=1)
    assert result is not None
    assert result['message_id'] == 'test-123'
```

#### **3.2. Testes de Integração**

```bash
# 1. Iniciar consumer Redis
python manage.py start_chat_consumer

# 2. Enfileirar mensagem de teste
python manage.py shell
>>> from apps.chat.tasks import send_message_to_evolution
>>> send_message_to_evolution.delay('test-message-id')

# 3. Verificar logs do consumer
# Deve aparecer: "📥 [REDIS CONSUMER] Recebida task send_message"
```

---

### **FASE 4: Deploy (30 min)**

#### **4.1. Checklist de Deploy**

- [ ] ✅ Código implementado e testado localmente
- [ ] ✅ Testes passando
- [ ] ✅ Redis Database 2 configurado
- [ ] ✅ Consumer Redis iniciando corretamente
- [ ] ✅ Logs mostrando mensagens sendo processadas

#### **4.2. Deploy em Produção**

```bash
# 1. Fazer commit das mudanças
git add .
git commit -m "feat: Migrar chat de RabbitMQ para Redis"
git push origin main

# 2. Deploy automático via Railway
# Railway vai:
# - Fazer build
# - Rodar migrations
# - Reiniciar aplicação
# - Consumer Redis inicia automaticamente via ASGI

# 3. Verificar logs
# Deve aparecer: "🚀 [REDIS CHAT] Iniciando Redis Chat Consumer..."
# Deve aparecer: "✅ [REDIS CONSUMER] Consumers iniciados!"
```

#### **4.3. Monitoramento Pós-Deploy**

```bash
# Verificar filas Redis
redis-cli -n 2 KEYS "chat:queue:*"

# Ver tamanho das filas
redis-cli -n 2 LLEN chat:queue:send_message
redis-cli -n 2 LLEN chat:queue:fetch_profile_pic
redis-cli -n 2 LLEN chat:queue:fetch_group_info

# Ver logs do consumer
# Deve processar mensagens normalmente
```

---

### **FASE 5: Limpeza (15 min)**

#### **5.1. Remover Código RabbitMQ Antigo**

```python
# backend/apps/chat/tasks.py

# ❌ REMOVER: Função delay() RabbitMQ
# ❌ REMOVER: start_chat_consumers() RabbitMQ
# ❌ REMOVER: Imports aio_pika, pika (se não usar mais)

# ✅ MANTER: handle_send_message(), handle_fetch_profile_pic() (handlers)
# ✅ MANTER: process_incoming_media (ainda usa RabbitMQ)
```

#### **5.2. Remover Dependências (opcional)**

```bash
# Se RabbitMQ não for mais usado em nenhum lugar:
# pip uninstall aio-pika pika

# Mas manter por enquanto (campanhas ainda usam)
```

---

## 📊 **COMPARAÇÃO ANTES/DEPOIS**

### **Antes (RabbitMQ):**

```
Latência: 15-65ms
Throughput: 10k-50k msg/s
Recursos: CPU médio, Disco alto
Complexidade: Alta (AMQP)
```

### **Depois (Redis):**

```
Latência: 2-6ms (10x mais rápido)
Throughput: 100k-500k msg/s (10x mais)
Recursos: CPU baixo, RAM alto
Complexidade: Baixa (RESP)
```

---

## 🔄 **ROLLBACK (Se Necessário)**

### **Plano de Rollback:**

```python
# 1. Reverter código para versão anterior
git revert <commit-hash>

# 2. Reiniciar aplicação
# Consumer RabbitMQ volta a funcionar automaticamente

# 3. Limpar filas Redis (opcional)
redis-cli -n 2 FLUSHDB
```

---

## ✅ **CHECKLIST FINAL**

### **Antes de Migrar:**

- [ ] ✅ Redis Database 2 configurado
- [ ] ✅ Código Redis implementado
- [ ] ✅ Testes passando
- [ ] ✅ Consumer Redis funcionando localmente

### **Durante Migração:**

- [ ] ✅ Deploy em produção
- [ ] ✅ Consumer Redis iniciando
- [ ] ✅ Mensagens sendo processadas
- [ ] ✅ Logs sem erros

### **Após Migração:**

- [ ] ✅ Monitorar latência (deve ser 10x mais rápido)
- [ ] ✅ Monitorar throughput
- [ ] ✅ Remover código RabbitMQ antigo
- [ ] ✅ Documentar mudanças

---

## 🎯 **RESULTADO ESPERADO**

### **Performance:**

- ✅ **Latência:** 15-65ms → 2-6ms (**10x mais rápido**)
- ✅ **Throughput:** 10x mais capacidade
- ✅ **UX:** Mensagens aparecem quase instantaneamente

### **Custo:**

- ✅ **Mesmo custo** (Redis já está configurado)
- ✅ **Menos CPU/disco** (mais eficiente)
- ✅ **Mais RAM** (mas Redis é muito rápido)

---

## 📝 **PRÓXIMOS PASSOS**

1. ✅ **Implementar código Redis** (Fase 1-2)
2. ✅ **Testar localmente** (Fase 3)
3. ✅ **Deploy em produção** (Fase 4)
4. ✅ **Monitorar performance** (Fase 5)
5. ✅ **Limpar código antigo** (Fase 5)

---

**Resultado:** Chat **10x mais rápido** usando Redis compartilhado! 🚀

