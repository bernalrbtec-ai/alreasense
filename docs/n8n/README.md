# Workflows n8n – Gestão RAG e Lembranças

Workflows alinhados ao [plano de fluxo n8n](../../.cursor/plans/) (Summarize, RAG upsert, RAG remove).

**Arquitetura:** Sense pede, n8n processa e devolve. Toda a IA (LLM, embedding, pgvector) fica na infra do n8n; o Sense mantém só gestão e chama webhooks.

## Arquivos

| Arquivo | Webhook path | Uso |
|---------|--------------|-----|
| `sense_summarize.json` | `summarize` | Backend chama ao fechar conversa; devolve `summary`, `subject`, `sentiment`, `satisfaction`. |
| `sense_rag_upsert.json` | `rag-upsert` | Backend chama ao aprovar resumo ou ao salvar perfil empresa; persiste no pgvector. |
| `sense_rag_remove.json` | `rag-remove` | Backend chama ao reprovar aprovado ou antes de reprocessar; remove do pgvector. |

## Como importar no n8n

1. No n8n: **Workflows** → **Import from File** (ou colar o JSON).
2. Ajustar em cada workflow:
   - **Summarize:** URL do LLM no nó "LLM Resumo" (ex.: Ollama `http://localhost:11434/api/generate`).
   - **RAG upsert:** substituir o nó placeholder por embedding + Postgres (pgvector).
   - **RAG remove:** substituir o nó placeholder por Postgres DELETE.
3. Ativar o workflow e configurar no backend as URLs dos webhooks (ex.: `https://seu-n8n/webhook/summarize`, etc.).

## Scripts SQL

| Onde | Script | Uso |
|------|--------|-----|
| **Sense** | [docs/SQL_conversation_summary.sql](../SQL_conversation_summary.sql) | Tabela de gestão `ai_conversation_summary`. Executar no PostgreSQL do Sense. |
| **n8n (infra IA)** | [docs/SQL_rag_pgvector.sql](../SQL_rag_pgvector.sql) | Tabela pgvector para RAG (rag-upsert/rag-remove). Executar no **PostgreSQL da infra n8n** (não no Sense). |

Ambos idempotentes (`IF NOT EXISTS`).
