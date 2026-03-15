# Maturidade para produção: instruções Typebot (#{...}) e fluxo

Avaliação objetiva do que foi implementado (instruções no texto, encerrar, transferir por nome, FAQ) e do que recomenda-se antes ou após subir para produção.

---

## O que está implementado

- **Instruções no texto:** Parse de `#{"chave": valor}` (até 500 caracteres), execução de encerrar/transferir e remoção do trecho antes de enviar ao WhatsApp.
- **Encerrar:** `closeTicket` / `encerrar` / `closeConversation` (truthy); mesma lógica do webhook (mensagens lidas, status=closed, department/assigned_to=None, remove estado).
- **Transferir:** `transferTo` / `transferToDepartment` com **nome do departamento** (tenant + name__iexact; nome com espaços); mensagem interna com sender=None, broadcast, transfer_message ao cliente, try_send_flow_start.
- **Segurança:** Fallback em exceção (usa textos originais); validação de conversation/tenant_id/texts; só remove trechos com chave conhecida e JSON válido; após encerrar não executa mais instruções no lote.
- **Webhook:** Fechar conversa por variável usa `close_conversation_from_typebot` (lógica única).
- **Doc e FAQ:** FLUXOS_TYPEBOT_GUIA com seção “Instruções no texto”; FAQ recolhível no modal Editar fluxo (FlowPage).

---

## Pontos sólidos para produção

| Aspecto | Situação |
|--------|----------|
| **Compatibilidade** | Fluxos sem `#{...}` seguem iguais; nenhuma mudança de contrato em start/continue. |
| **Degradação** | Erro no processamento de instruções não quebra o envio: usa lista original e loga warning. |
| **Dados** | Close e transfer usam transação atômica; conversation.refresh_from_db() após alterar. |
| **Entrada** | texts não-lista retorna []; conversation/tenant_id validados; item não-string tratado. |
| **Transferência** | Departamento não encontrado só loga; envio da mensagem ao cliente em try/except (falha não invalida a transferência). |
| **Ordem** | Após executar “encerrar”, não executa mais instruções no mesmo lote. |
| **Parse** | Segmento JSON com `{` e `}`; limite 500 chars; json.loads em try/except. |

---

## Riscos e limitações aceitáveis

| Item | Risco | Mitigação |
|------|--------|------------|
| **`}` no valor** | `#{"x": "}"}` quebra o parse (primeiro `}` fecha). | Aceitável; valor com `}` não é suportado; trecho não é removido (cliente pode ver). |
| **Sem testes automatizados** | Regressão em refator futura. | Testes manuais (guia no plano); considerar depois testes unitários para _process_instructions_in_texts e close/transfer. |
| **Nome do departamento** | Nome errado ou alterado no Sense não transfere. | Só log; FAQ/doc explicam usar nome igual ao cadastrado. |
| **Mensagem após fechar** | Se Typebot enviar texto + closeTicket, as mensagens do lote ainda são enfileiradas (conversa já fechada). | Comportamento definido no plano; opcionalmente no futuro pular envio quando close for executado. |

---

## Recomendações antes de produção

1. **Testes manuais** (mínimo):
   - Fluxo só texto, sem `#{...}` (comportamento igual ao atual).
   - Texto + `#{"closeTicket": true}`: conversa fecha e cliente não vê a instrução.
   - Texto + `#{"transferTo": "Nome do Dept"}`: conversa vai para o departamento e cliente recebe só o texto.
   - Nome de departamento inexistente: log de aviso e conversa não transferida.

2. **Monitoramento:** Buscar nos logs por `[TYPEBOT]` (erros, “Departamento não encontrado”, “Erro ao processar instruções”) nas primeiras semanas.

3. **Documentação:** Garantir que a equipe que configura Typebot conheça a seção “Instruções no texto” no guia e a FAQ no modal Editar fluxo.

---

## Recomendações pós-produção (opcional)

- Testes unitários para `_process_instructions_in_texts` (vários textos, close, transfer, chave desconhecida, JSON inválido) e para `close_conversation_from_typebot` / `_execute_transfer_by_department_name`.
- Métricas/monitoramento: contagem de instruções processadas (close/transfer) por dia ou por tenant.
- Se surgir necessidade de valor com `}` no JSON, considerar parser que respeite strings entre aspas.

---

## Veredicto

- **Pode ir para produção** desde que:
  - Os testes manuais acima forem feitos.
  - Houver acompanhamento de logs nos primeiros dias.
  - Os usuários que configuram Typebot tiverem acesso ao guia e à FAQ (nome do departamento, formato das instruções).

- **Maturidade:** adequada para produção com monitoramento inicial; evolução natural é adicionar testes automatizados e métricas depois.
