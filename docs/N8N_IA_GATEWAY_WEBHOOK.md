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
  "send_to_chat": true,  // se true e conversation_id fornecido, envia resposta ao chat
  "prompt": "Você é um assistente...",  // opcional: prompt de sistema/instrução para o teste
  "knowledge_items": [   // opcional: contexto RAG para o teste (até 5 itens)
    { "title": "Doc.txt", "content": "Texto do documento...", "source": "test_upload" }
  ]
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
  },
  "prompt": "Você é um assistente...",
  "knowledge_items": [
    { "title": "Doc.txt", "content": "Texto do documento...", "source": "test_upload" }
  ]
}
```

- **prompt** (string, opcional): quando presente, use como prompt de sistema/instrução no teste.
- **knowledge_items** (array, opcional): lista de `{ title, content, source }` para contexto RAG no teste; injete no contexto do modelo (ex.: concatenar ao prompt ou usar em passo de RAG).

### 2. Resposta obrigatória do webhook

O Sense espera que o n8n **responda à requisição HTTP** (o webhook) com um JSON no corpo da resposta. O timeout do Sense é 10 segundos; responda dentro desse tempo.

**Formato obrigatório da resposta (JSON):**

| Campo        | Obrigatório | Descrição |
|-------------|-------------|-----------|
| `reply_text` ou `text` | Sim* | Texto da resposta da IA. O Sense usa `reply_text` primeiro; se não existir, usa `text`. |
| `status`    | Não  | Use `"success"` em caso de sucesso. Se for outro valor ou `"error"`, o Sense trata como falha e pode retornar 400. |
| `meta`      | Não  | Objeto com `model`, `latency_ms`, `rag_hits`, `prompt_version` (todos opcionais). **Se enviar `meta`, deve ser um objeto** (nunca `null`), senão o Sense pode falhar. |

\* Se não houver `reply_text` nem `text`, o Sense considera resposta vazia (pode não enviar ao chat).

**Exemplo de resposta de sucesso:**

```json
{
  "reply_text": "Olá! Como posso ajudar?",
  "status": "success",
  "meta": {
    "model": "llama-3.1-8b",
    "latency_ms": 1200,
    "rag_hits": 2,
    "prompt_version": "v1"
  }
}
```

**Exemplo de resposta de erro (Sense trata como falha e retorna 400):**

```json
{
  "status": "error",
  "error_code": "MODEL_ERROR",
  "error_message": "Modelo indisponível"
}
```

### 3. Processar com IA/RAG

- Se existir `payload.prompt`, use como **instrução de sistema** do modelo.
- Se existir `payload.knowledge_items`, monte o **contexto** (ex.: concatenar `title` + `content` de cada item) e inclua no prompt ou em passo de RAG.
- Mensagem do usuário: `payload.message.content`.
- Chame o modelo de IA (Ollama, OpenAI, etc.) e obtenha o texto de resposta.

**Montagem sugerida do prompt enviado ao modelo:**

1. **System:** `payload.prompt` (se existir), senão um texto padrão (ex.: "Você é um assistente prestativo.").
2. **Contexto RAG:** se `payload.knowledge_items` existir, para cada item: `## ${item.title}\n${item.content}` e concatene com quebras de linha.
3. **Usuário:** `payload.message.content`.

Exemplo em JavaScript (para usar em nó **Code** do n8n):

```javascript
const body = $input.first().json;
const systemPrompt = body.prompt && body.prompt.trim() ? body.prompt.trim() : 'Você é um assistente prestativo.';
const knowledgeItems = body.knowledge_items || [];
const context = knowledgeItems.map(i => `## ${i.title}\n${i.content}`).join('\n\n');
const userMessage = (body.message && body.message.content) ? body.message.content : '';
const fullPrompt = [
  systemPrompt,
  context ? `Contexto para consulta:\n${context}` : '',
  `Mensagem do usuário: ${userMessage}`
].filter(Boolean).join('\n\n');

const model = (body.metadata && body.metadata.model) ? body.metadata.model : 'llama-3.1-8b';
// Use fullPrompt e model na chamada ao Ollama/OpenAI; depois devolva:
// { reply_text: "...", status: "success", meta: { model, latency_ms } }
```

**Importante:** o nó **Webhook** do n8n deve estar configurado para **Responder quando o último nó terminar** (Response Mode: "When Last Node Finishes"). O último nó do fluxo deve devolver um único item cujo JSON seja exatamente o formato de resposta obrigatória (ex.: um nó **Code** que monta `{ reply_text, status, meta }` e retorna). Assim o Sense recebe a resposta na mesma chamada HTTP ao webhook.

### 4. Enviar Resposta ao Chat (produção)

Quando o Sense quiser enviar a resposta ao chat (ex.: teste com "Enviar resposta ao chat"), ele usa o `reply_text` que você devolveu e chama o endpoint `/api/ai/gateway/reply/` internamente. Você **não** precisa chamar esse endpoint a partir do n8n no fluxo de teste; basta devolver o JSON com `reply_text`. Se no futuro quiser que o n8n envie direto ao chat (ex.: em produção com outra ação), use:

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

### 5. Resposta Esperada do /api/ai/gateway/reply/

```json
{
  "status": "success",
  "message_id": "uuid",
  "conversation_id": "uuid"
}
```

## Workflow n8n pronto (Gateway IA – teste com prompt e RAG)

Há um workflow de exemplo que você pode importar no n8n: **[n8n_workflow_ia_gateway.json](n8n_workflow_ia_gateway.json)**.

Ele tem 4 nós:

1. **Webhook Sense IA** (POST) – recebe o payload do Sense (message, prompt, knowledge_items, metadata). Responde quando o último nó terminar.
2. **Montar prompt e modelo** (Code) – monta o prompt (system + contexto RAG + mensagem do usuário) e devolve `fullPrompt`, `model` e `knowledgeItemsCount`.
3. **Chamar Ollama** (HTTP Request) – POST para `/api/generate` no Ollama. **Use aqui a sua credencial já salva no n8n** (Ollama ou HTTP Request com a URL do seu Ollama).
4. **Formatar resposta para o Sense** (Code) – monta o JSON que o Sense espera: `reply_text`, `status: "success"`, `meta` (model, latency_ms, rag_hits).

**Configuração após importar:**

- No nó **Chamar Ollama**: selecione a sua credencial (ex.: credencial Ollama ou HTTP com URL do Ollama) e ajuste a **URL** para o endpoint do Ollama (ex.: `http://localhost:11434/api/generate` ou a base da credencial + `/api/generate`). Não é necessário usar variável de ambiente; a URL pode vir da própria credencial.
- O **path do Webhook** (ex.: `sense-ia-gateway`) deve bater com a URL que você configurar no Sense em **Configurações > Agentes IA > Webhook do Gateway IA** (a URL completa que o Sense chama).

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
