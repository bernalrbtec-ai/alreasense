# 🧹 Como Limpar a Fila RabbitMQ `chat_process_incoming_media`

## ⚠️ PROBLEMA IDENTIFICADO

A fila `chat_process_incoming_media` tem **399 mensagens presas** porque o consumer não estava rodando.

## 🔧 SOLUÇÃO: Limpar a Fila

### Opção 1: Via RabbitMQ Management UI (Recomendado)

1. Acesse o RabbitMQ Management UI (geralmente em `http://seu-rabbitmq:15672`)
2. Vá em **Queues**
3. Encontre a fila `chat_process_incoming_media`
4. Clique na fila
5. Na aba **Messages**, clique em **Purge Messages**
6. Confirme a ação

### Opção 2: Via RabbitMQ HTTP API

```bash
# Substitua USERNAME, PASSWORD e HOST pelos valores corretos
curl -u USERNAME:PASSWORD -X DELETE \
  http://HOST:15672/api/queues/%2F/chat_process_incoming_media/contents
```

### Opção 3: Via Python (Django Shell)

```python
# No Django shell (python manage.py shell)
import pika
from django.conf import settings

# Conectar ao RabbitMQ
connection = pika.BlockingConnection(
    pika.URLParameters(settings.RABBITMQ_URL)
)
channel = connection.channel()

# Limpar a fila
channel.queue_purge('chat_process_incoming_media')

print(f"✅ Fila limpa!")

connection.close()
```

### Opção 4: Via Railway CLI (se usar Railway)

```bash
# Conectar ao serviço RabbitMQ
railway connect

# Usar rabbitmqadmin (se disponível)
rabbitmqadmin purge queue name=chat_process_incoming_media
```

## ✅ APÓS LIMPAR

1. **Deploy da correção**: O novo consumer RabbitMQ será iniciado automaticamente
2. **Verificar logs**: Confirme que o consumer está rodando
3. **Testar**: Envie uma mensagem com anexo e verifique se é processada

## 📊 Verificação

Após limpar e iniciar o consumer, verifique:

1. **RabbitMQ UI**: A fila deve ter `Ready: 0`
2. **Logs do backend**: Deve aparecer `🚀 [CHAT CONSUMER] Consumers iniciados`
3. **MinIO**: Novos anexos devem aparecer após processamento

## ⚠️ IMPORTANTE

- **NÃO limpe outras filas** (elas podem ter mensagens válidas)
- **Apenas limpe `chat_process_incoming_media`** (as 399 mensagens são antigas e não serão processadas corretamente)
- **Após limpar**, novas mensagens serão processadas normalmente

