## Objetivo

Definir instruções lógicas e técnicas para concluir a tela de teste do Gateway IA (app -> n8n -> LLM -> n8n -> app), padronizar o contrato de payload entre app e n8n, e implementar auditoria completa das ações de IA no app. Este documento é para execução por um próximo agente.

## Escopo desta etapa

- Finalizar o modal de teste da integração IA na configuração.
- Definir contrato de payload e resposta entre app e n8n.
- Implementar auditoria completa no app para ações de IA.
- Manter o n8n como orquestrador central de IA (LLM + RAG).
- RAG e memória são por tenant (sempre isolados), mesmo quando o agente for global.

## Premissas e decisões

- A IA é centralizada no n8n; o app apenas aciona e registra auditoria.
- O n8n é responsável por:
  - escolher LLM
  - executar RAG com pgvector
  - buscar histórico e memória do tenant
- O app deve registrar auditoria oficial e durável (compliance + debug).
- Logs no n8n são operacionais e não substituem auditoria no app.
- Um departamento pode ter N agentes; a orquestração (router) é no n8n.
- A triagem global é o único agente global (prompt global), mas o RAG é sempre por tenant.

## Contrato do Gateway IA (app -> n8n)

### Endpoint (n8n)
Definir no n8n um webhook HTTP(s) para receber o payload.

### Payload mínimo recomendado
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
    "content": "texto",
    "created_at": "ISO8601"
  },
  "metadata": {
    "source": "test",
    "model": "opcional",
    "app_version": "opcional"
  }
}
```

### Observações
- `tenant_id` é obrigatório e deve ser validado.
- `request_id` + `trace_id` são obrigatórios para auditoria.
- Não enviar PII no payload. O n8n busca o que precisa usando `tenant_id`.
- `agent_id` e `department_id` devem estar presentes para futura orquestração.
- `message.direction` deve ser `"incoming"` ou `"outgoing"`.
- `request_id` deve ser idempotente por tentativa (evita duplicar auditoria).

## Resposta esperada (n8n -> app)

```json
{
  "status": "success",
  "request_id": "uuid",
  "trace_id": "uuid",
  "reply_text": "texto",
  "confidence": 0.0,
  "handoff": false,
  "handoff_reason": "user_request|confidence_low|other",
  "actions": [],
  "meta": {
    "model": "string",
    "latency_ms": 0,
    "rag_hits": 0,
    "prompt_version": "string"
  }
}
```

### Erros (padrão)
```json
{
  "status": "error",
  "request_id": "uuid",
  "trace_id": "uuid",
  "error_code": "string",
  "error_message": "string",
  "meta": {
    "model": "string",
    "latency_ms": 0,
    "rag_hits": 0
  }
}
```

### Schema de `actions` (sugestão)
```json
[
  {
    "type": "tag_contact|create_task|handoff|other",
    "id": "uuid",
    "status": "queued|executed|failed",
    "payload": {},
    "error_code": "string",
    "error_message": "string"
  }
]
```

### Tabela sugerida de `error_code`
- `INVALID_PROTOCOL_VERSION`
- `MISSING_TENANT_ID`
- `INVALID_REQUEST`
- `UNAUTHORIZED`
- `RATE_LIMITED`
- `TIMEOUT`
- `UPSTREAM_ERROR`
- `INTERNAL_ERROR`

## Auditoria (app)

### Objetivo
Registrar todas as ações de IA e decisões (inclusive testes) para compliance, debug e métricas.

### Campos obrigatórios sugeridos
- tenant_id
- conversation_id
- message_id
- contact_id
- department_id
- agent_id
- request_id
- trace_id
- status (success/failed)
- model
- latency_ms
- rag_hits
- prompt_version
- input_summary
- output_summary
- handoff (bool)
- handoff_reason
- error_code
- error_message
- request_payload_masked
- response_payload_masked
- created_at

### Requisitos
- Auditoria deve existir mesmo quando a mensagem final já estiver no chat.
- Auditoria deve ser salva no app (fonte de verdade).
- Logs do n8n são complementares (operacionais).
- Armazenar payloads mascarados (não salvar PII em texto puro).

## Regras de segurança e profissionalismo

- Validar `tenant_id` e rejeitar payload sem esse campo.
- Incluir `protocol_version` no payload e rejeitar versões desconhecidas.
- Mascarar PII em logs.
- Usar timeouts curtos nas chamadas do app ao n8n.
- Padronizar erros com `error_code` e `error_message`.
- Proteger endpoints de teste com autenticação e rate limit.
- Registrar `request_id` e `trace_id` em toda chamada.
- Definir política de retry (ex.: 1 retry com backoff curto).

## UI: Modal de teste do Gateway IA

### Requisitos visuais e funcionais
- Campo de mensagem para teste.
- Seleção de modelo (se disponível).
- Exibir request enviado (com dados mascarados).
- Exibir response recebido (status, latency, model, rag_hits).
- Exibir erros padronizados.
- Exibir `request_id` e `trace_id`.
- Indicar se a resposta gerou handoff e o motivo.

### Fluxo
1. Usuário clica em “Testar IA” na configuração.
2. App monta payload (com `tenant_id`, `request_id`, `trace_id`).
3. App envia para o webhook do n8n.
4. App recebe resposta e registra auditoria.
5. UI mostra resultado completo.

## Fluxo n8n (alto nível)

1. Receber payload do app.
2. Validar `tenant_id` e `protocol_version`.
3. Buscar histórico e memória no pgvector (por tenant).
4. Executar RAG e montar contexto.
5. Chamar LLM.
6. Retornar resposta padronizada ao app.
7. Registrar logs técnicos (n8n).

## Observações finais

- O RAG deve ser exclusivo por tenant.
- O agente global é apenas “prompt global”; o RAG é sempre por tenant.
- Um departamento pode ter múltiplos agentes, com orquestrador no n8n.
 
