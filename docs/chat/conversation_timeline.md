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
- Takeover Dify: `apps/ai/services/dify_chat_service.py` busca em `ai_knowledge_document` (`source=chat_text_transcript`, `metadata.contact_phone` normalizado) dentro de `rag_lookback_months` e injeta o texto no **input** do app cujo nome de variável está em `rag_context_input_key` (catálogo do agente). A conversa **aberta** não entra nesses documentos até o próximo fechamento; o modelo Dify mantém o **histórico da sessão atual** via `conversation_id` da API Dify.
- **Episódio Dify** (`metadata.dify_episode_id`, ms UTC): definido na criação da conversa e **renovado** quando o status sai de `closed` (reabertura). O campo `user` enviado ao Dify inclui tenant + app + telefone + episódio, para cada ciclo fechamento/reabertura no Sense corresponder a uma **nova** conversa no Dify; ao reabrir, zera-se `dify_conversation_id` em `ai_dify_conversation_state` (ver `apps/chat/signals.py`).
- Futuro: API, export, UI

### Catálogo Dify (metadata)

| Campo | Efeito |
|-------|--------|
| `rag_enabled` | Liga a busca de transcripts fechados no takeover. |
| `rag_lookback_months` | Janela em meses sobre `created_at` do documento (1–120, default 12). |
| `rag_context_input_key` | Nome exato da variável de entrada no app Dify; se vazio, nada é injetado (evita 400). |

Limites globais: `DIFY_RAG_CONTEXT_TOP_K`, `DIFY_RAG_CONTEXT_MAX_CHARS`, `DIFY_RAG_CONTEXT_SIMILARITY`, `DIFY_RAG_CONTEXT_CHRONOLOGICAL` (default `True`: ordena os hits por `closed_at` crescente antes de montar o texto) em `settings.py`.

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
