# -*- coding: utf-8 -*-
"""Aplica correções no plano que falham por aspas curvas/Unicode."""
import re

path = r"c:\Users\paulo\.cursor\plans\fluxo_n8n_gestão_rag_e_lembranças_019293be.plan.md"

with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# 1) Remover linha residual " que \"x\"." (aspas curvas \u201c \u201d)
text = text.replace("\n que \u201cx\u201d.\n", "\n")

# 1b) Fluxo 2: remover trecho final da linha "Nós n8n" (aspas curvas)
old_nos = " → Responder (When Last Node Finishes). \u201cResuma esta conversa. Mensagens: \u2026\u201d)."
new_nos = " → Responder (When Last Node Finishes)."
if old_nos in text:
    text = text.replace(old_nos, new_nos)

# 2) Fluxo 4: remover desde " REMOVED" até o "\n\n---" seguinte (bloco Opção A/B e parágrafo)
idx_removed = text.find(" REMOVED")
if idx_removed != -1:
    idx_fluxo4_end = text.find("\n\n---", idx_removed)
    if idx_fluxo4_end != -1:
        text = text[:idx_removed] + text[idx_fluxo4_end:]

# 4) Substituir seção "Revisão: pontos de falha e melhorias" por "Riscos e mitigações" (tabela + parágrafo)
riscos_block = r'## Revisão: pontos de falha e melhorias\n\n\*\*Resumo:\*\*[^\n]+\n\n### Possíveis pontos de falha\n\n(?:\d+\. \*\*[^\*]+\*\*[^\n]*\n(?:   [^\n]+\n)*)*\n### Melhorias sugeridas \(prioridade\)\n\n(?:\*\*[^\*]+\*\*:?\n\n)?(?:- \*\*[^\*]+\*\*[^\n]*\n)*\n(?:\*\*[^\*]+\*\*:?\n\n)?(?:- [^\n]*\n)*\n(?:\*\*[^\*]+\*\*:?\n\n)?(?:- [^\n]*\n)*'

nova_secao = '''## Riscos e mitigações

| Risco | Mitigação |
|-------|------------|
| Aprovar no Sense e rag-upsert falhar (inconsistência) | Retry no backend (2x backoff); opcional: UI "Reenviar para memória". |
| RAG remove não configurado (fantasmas no pgvector) | Configurar `N8N_RAG_REMOVE_WEBHOOK_URL`; ou rag-upsert fazer replace por (tenant_id, source, conversation_id). |
| Duplo summarize (corrida ao fechar) | `update_or_create` garante uma linha; custo é 2 chamadas n8n. Opcional: lock em metadata. |
| Company sync duplicatas | n8n: `source=company` = replace (DELETE + INSERT) por tenant+source. |
| Reprocess: summarize falha após remove | Aceitável; reprocessar de novo repõe. |
| Conteúdo grande (embedding/LLM) | n8n truncar com aviso; backend limita edit a 65535 chars. |
| rag-remove com doc inexistente | n8n responder sempre 200 (idempotente). |
| Threads daemon (processo termina) | Aceitável em servidor estável; opcional: fila (RabbitMQ). |

**Melhorias prioritárias:** Retry em `_rag_upsert_for_summary` e `_rag_remove_for_summary` (2x backoff, ver [rag_sync](backend/apps/tenancy/rag_sync.py)); contrato de erro n8n (`status`, `code`, `message`); observabilidade (trace_id por chamada).

'''

# Substituir seção Revisão por Riscos e mitigações (usar aspas curvas no marker)
start_marker = "## Revisão: pontos de falha e melhorias"
end_marker = "--- \u201cum documento por tenant\u201d"  # aspas curvas Unicode
idx_start = text.find(start_marker)
idx_end = text.find(end_marker)
new_section = """## Riscos e mitigações

| Risco | Mitigação |
|-------|------------|
| Aprovar no Sense e rag-upsert falhar (inconsistência) | Retry no backend (2x backoff); opcional: UI "Reenviar para memória". |
| RAG remove não configurado (fantasmas no pgvector) | Configurar `N8N_RAG_REMOVE_WEBHOOK_URL`; ou rag-upsert fazer replace por (tenant_id, source, conversation_id). |
| Duplo summarize (corrida ao fechar) | `update_or_create` garante uma linha; custo é 2 chamadas n8n. Opcional: lock em metadata. |
| Company sync duplicatas | n8n: `source=company` = replace (DELETE + INSERT) por tenant+source. |
| Reprocess: summarize falha após remove | Aceitável; reprocessar de novo repõe. |
| Conteúdo grande (embedding/LLM) | n8n truncar com aviso; backend limita edit a 65535 chars. |
| rag-remove com doc inexistente | n8n responder sempre 200 (idempotente). |
| Threads daemon (processo termina) | Aceitável em servidor estável; opcional: fila (RabbitMQ). |

**Melhorias prioritárias:** Retry em `_rag_upsert_for_summary` e `_rag_remove_for_summary` (2x backoff, ver [rag_sync](backend/apps/tenancy/rag_sync.py)); contrato de erro n8n (`status`, `code`, `message`); observabilidade (trace_id por chamada).

"""
if idx_start != -1 and idx_end != -1:
    ref_pos = text.find("## Referências", idx_end)
    text = text[:idx_start] + new_section + "\n---\n\n" + (text[ref_pos:] if ref_pos != -1 else "")


with open(path, "w", encoding="utf-8") as f:
    f.write(text)

print("OK: plano atualizado.")
