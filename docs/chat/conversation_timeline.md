# Conversation timeline (operational log)

Eventos append-only em `conversation.metadata["conversation_timeline_events"]`, mesclados com mensagens na renderização usada pelo RAG (`render_timeline_plaintext`).

## Contrato (schema_version 1)

Cada evento:

- `at`: ISO8601 (timezone-aware)
- `type`: string estável (ver `apps/chat/services/conversation_timeline.py`)
- `schema_version`: int
- `data`: objeto por tipo

Tipos MVP:

| type | Significado |
|------|-------------|
| `conversation_opened` | Nova conversa / início rastreado |
| `conversation_reopened` | De `closed` para `open`/`pending` |
| `assignment_changed` | `assigned_to` alterado |
| `department_transfer` | Troca de departamento |
| `conversation_closed` | Fechamento com snapshot de dept/atendente **antes** de limpar FKs |

Limite: últimos `MAX_TIMELINE_EVENTS` (200); metadado `conversation_timeline_truncated` se houve corte.

Grupos WhatsApp (`g.us` no telefone): não gravam eventos (alinhado ao RAG).

## Consumidores

- Ingestão RAG ao fechar: `apps/ai/services/dify_rag_memory_service.py` → `render_timeline_plaintext`
- Futuro: API, export, UI

## Variáveis de ambiente (produção)

| Variável | Default | Efeito |
|----------|---------|--------|
| `CHAT_CONVERSATION_TIMELINE_ENABLED` | `True` | `False`: não grava eventos (mensagens e RAG continuam; RAG pode usar só mensagens se render habilitado). |
| `CHAT_TIMELINE_RAG_RENDER_ENABLED` | `True` | `False`: texto embeddado para RAG **ignora** eventos e usa só linhas de mensagem (útil se eventos estiverem ruidosos). |

Definidas em `alrea_sense/settings.py` via `python-decouple`.

## Observabilidade

- Falha ao persistir evento: log **ERROR** com prefixo `[conversation_timeline] persist_failed` e `conversation_id`, `event_type`.
- Falha na ingestão RAG do transcript: log **ERROR** `[rag_transcript] ingest_failed`.

Configure alertas no agregador de logs filtrando esses prefixos.

## Runbook rápido

1. **Desligar só a escrita de eventos** (emergência): `CHAT_CONVERSATION_TIMELINE_ENABLED=false` e redeploy.
2. **Manter eventos no metadata mas RAG só com chat**: `CHAT_TIMELINE_RAG_RENDER_ENABLED=false`.
3. **Desligar ingest RAG** (já existente): `rag_enabled` no catálogo Dify + sinais; não altera timeline.
4. **Limpar timeline corrompida** (manual): PATCH/Admin em `conversation.metadata` removendo ou corrigindo `conversation_timeline_events` (backup antes).
5. **Retenção documentos RAG**: comando `cleanup_dify_rag_transcripts` no cron (já documentado no app `ai`).

## Cobertura de hooks

- Fechamento: API, `close_conversation_from_bot`, welcome menu, inbox idle.
- Abertura/reabertura: API `conversation_start`, `reopen`, **webhook** (nova conversa + reabrir de `closed`).
- Atribuição: `claim`, `start_attendance`, WebSocket auto-assign.
- Transferência: `flow_control.transfer_conversation_to_department`.

Outros criadores de `Conversation` (campanhas, Meta, etc.) podem não emitir `conversation_opened` até haver hook dedicado.
