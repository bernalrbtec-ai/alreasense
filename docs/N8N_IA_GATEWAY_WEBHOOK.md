# N8N IA Gateway Webhook - Documentação

Este documento descreve como configurar o fluxo no n8n para receber chamadas da IA/RAG e enviar respostas diretamente ao chat.

## Visão Geral

O sistema permite que o n8n:
1. Receba chamadas do Gateway IA (via webhook configurado em `TenantAiSettings.n8n_ai_webhook_url`)
2. Processe a requisição com IA/RAG
3. Envie a resposta diretamente ao chat usando o endpoint `/ai/gateway/reply/`

## Fluxo de Teste (Modal de Configurações)

### 1. Teste via Modal

No modal de teste (`Configurações > Agentes IA > Testar IA`):
- Selecione uma conversa existente
- Marque "Enviar resposta da IA diretamente ao chat"
- Envie uma mensagem de teste
- A resposta da IA será enviada automaticamente ao chat selecionado

### 2. Endpoint de Teste

**POST** `/api/ai/gateway/test/`

**Body:**
```json
{
  "message": "Olá, preciso de ajuda",
  "model": "llama-3.1-8b",
  "conversation_id": "uuid-da-conversa",  // opcional
  "send_to_chat": true  // se true e conversation_id fornecido, envia resposta ao chat
}
```

**Response:**
```json
{
  "status": "success",
  "request_id": "uuid",
  "trace_id": "uuid",
  "data": {
    "request": { ... },
    "response": {
      "reply_text": "Olá! Como posso ajudar?",
      "status": "success",
      "meta": {
        "model": "llama-3.1-8b",
        "latency_ms": 1234,
        "rag_hits": 3
      }
    }
  }
}
```

## Fluxo N8N → Chat (Produção)

### Endpoint para N8N Enviar Resposta ao Chat

**POST** `/api/ai/gateway/reply/`

**Autenticação:** Requer token JWT (mesmo token usado nas outras APIs)

**Body:**
```json
{
  "conversation_id": "uuid-da-conversa",
  "reply_text": "Texto da resposta da IA",
  "request_id": "uuid",  // opcional, para rastreamento
  "trace_id": "uuid",     // opcional, para rastreamento
  "metadata": {           // opcional
    "model": "llama-3.1-8b",
    "latency_ms": 1234,
    "rag_hits": 3,
    "prompt_version": "v1"
  }
}
```

**Response (201 Created):**
```json
{
  "status": "success",
  "message_id": "uuid-da-mensagem-criada",
  "conversation_id": "uuid-da-conversa"
}
```

**Erros:**

- `400 Bad Request`: `conversation_id` ou `reply_text` ausentes
- `404 Not Found`: Conversa não encontrada ou não pertence ao tenant
- `500 Internal Server Error`: Erro ao criar mensagem

## Exemplo de Fluxo N8N

### 1. Webhook de Entrada (recebe chamada do Gateway IA)

**Trigger:** Webhook (POST)

**URL:** Configurado em `TenantAiSettings.n8n_ai_webhook_url`

**Payload recebido:**
```json
{
  "protocol_version": "v1",
  "action": "chat",
  "request_id": "uuid",
  "trace_id": "uuid",
  "tenant_id": "uuid",
  "conversation_id": "uuid",
  "contact_id": "uuid",
  "department_id": "uuid",
  "agent_id": "uuid",
  "message": {
    "id": "uuid",
    "direction": "incoming",
    "content": "Olá, preciso de ajuda",
    "created_at": "2025-02-04T10:00:00Z"
  },
  "metadata": {
    "source": "test",
    "model": "llama-3.1-8b"
  }
}
```

### 2. Processar com IA/RAG

- Buscar contexto relevante (RAG)
- Chamar modelo de IA
- Gerar resposta

### 3. Enviar Resposta ao Chat

**HTTP Request Node:**

- **Method:** POST
- **URL:** `{{ $env.API_BASE_URL }}/api/ai/gateway/reply/`
- **Headers:**
  ```
  Authorization: Bearer {{ $env.API_TOKEN }}
  Content-Type: application/json
  ```
- **Body (JSON):**
  ```json
  {
    "conversation_id": "{{ $json.conversation_id }}",
    "reply_text": "{{ $json.ai_response }}",
    "request_id": "{{ $json.request_id }}",
    "trace_id": "{{ $json.trace_id }}",
    "metadata": {
      "model": "{{ $json.model_used }}",
      "latency_ms": {{ $json.processing_time_ms }},
      "rag_hits": {{ $json.rag_hits }},
      "prompt_version": "v1"
    }
  }
  ```

### 4. Resposta Esperada

```json
{
  "status": "success",
  "message_id": "uuid",
  "conversation_id": "uuid"
}
```

## Variáveis de Ambiente N8N

Configure no n8n:

- `API_BASE_URL`: URL base da API (ex: `https://api.sense.com.br`)
- `API_TOKEN`: Token JWT de um usuário admin do tenant

## Observações Importantes

1. **Autenticação**: O endpoint `/ai/gateway/reply/` requer autenticação JWT válida
2. **Tenant Isolation**: A conversa deve pertencer ao mesmo tenant do usuário autenticado
3. **WebSocket**: A mensagem será automaticamente broadcastada via WebSocket para aparecer em tempo real no chat
4. **Evolution API**: A mensagem será automaticamente enviada ao WhatsApp via Evolution API (via RabbitMQ)
5. **Audit Log**: Se `request_id`/`trace_id` forem fornecidos, o evento será registrado em `AiGatewayAudit`

## Exemplo Completo de Workflow N8N

```json
{
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "httpMethod": "POST",
        "path": "ai-gateway"
      }
    },
    {
      "name": "Processar IA",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "http://localhost:11434/api/generate",
        "bodyParameters": {
          "model": "llama-3.1-8b",
          "prompt": "{{ $json.message.content }}"
        }
      }
    },
    {
      "name": "Enviar ao Chat",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "{{ $env.API_BASE_URL }}/api/ai/gateway/reply/",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "Authorization": "Bearer {{ $env.API_TOKEN }}"
        },
        "bodyParameters": {
          "conversation_id": "{{ $json.conversation_id }}",
          "reply_text": "{{ $json.response }}",
          "request_id": "{{ $json.request_id }}",
          "trace_id": "{{ $json.trace_id }}"
        }
      }
    }
  ]
}
```

## Troubleshooting

### Erro 401 Unauthorized
- Verifique se o token JWT está válido e não expirou
- Verifique se o header `Authorization: Bearer <token>` está correto

### Erro 404 Not Found
- Verifique se o `conversation_id` existe
- Verifique se a conversa pertence ao mesmo tenant do usuário autenticado

### Mensagem não aparece no chat
- Verifique os logs do backend para erros de WebSocket
- Verifique se o RabbitMQ está funcionando (para envio ao WhatsApp)
- Verifique se a conversa está aberta no frontend

### Mensagem não é enviada ao WhatsApp
- Verifique se o RabbitMQ está funcionando
- Verifique os logs do worker (`apps.chat.tasks.send_message_to_evolution`)
- Verifique se a instância WhatsApp está conectada
