# Overview: Fluxos (lista e botões)

## O que está implementado

### Backend
- **Modelos** (`apps/chat/models_flow.py`): `Flow`, `FlowNode`, `FlowEdge`, `ConversationFlowState`. Fluxo por tenant, escopo Inbox ou departamento.
- **Schema SQL** (`flow_schema.sql`): Tabelas idempotentes; migration 0017 aplica o SQL e mantém o state do Django.
- **Motor** (`services/flow_engine.py`):
  - `get_active_flow_for_conversation`: fluxo ativo por escopo (inbox vs departamento).
  - `get_start_node`: nó inicial (is_start ou menor order).
  - `send_flow_node`: cria mensagem com lista/botões e enfileira envio (task Evolution/Meta).
  - `process_flow_reply`: processa resposta (list_reply/button_reply), match por option_id normalizado, avança nó / transferência / encerramento.
  - `try_send_flow_start`: envia nó inicial em conversa nova ou reaberta; respeita `allow_meta_interactive_buttons`; não reenvia se já existir estado.
  - **Typebot**: quando `Flow.typebot_public_id` está preenchido, a execução é feita por `services/typebot_flow_service.py` (startChat/continueChat); o disparo continua igual (nova conversa, reabertura, transferência, botão Iniciar fluxo). O motor continua respeitando `allow_meta_interactive_buttons` do tenant antes de iniciar qualquer fluxo.
- **Webhook** (`webhooks.py`): Grava `list_reply`/`button_reply` em `message.metadata`; chama `process_flow_reply` (ou `continue_typebot_flow` se sessão Typebot ativa) antes do Welcome Menu; em conversa nova/reaberta chama `try_send_flow_start` antes de `send_welcome_menu`.
- **API** (`api/views.py`: endpoint **start-flow** no ConversationViewSet; `api/views_flow.py`, `serializers_flow.py`): CRUD de flows, flow-nodes, flow-edges; filtro por tenant; `send_test` e `available_departments`; `POST /chat/conversations/{id}/start-flow/` reinicia o fluxo do escopo; validações (body_text, sections, buttons, to_node mesmo fluxo, etc.).
- **Admin** (`admin.py`): Flow, FlowNode, FlowEdge registrados; visíveis só para `role=admin` (ou superuser); querysets filtrados por tenant.

### Frontend
- **FlowPage** (`pages/FlowPage.tsx`): Lista fluxos, criar fluxo, seleção pós-criar, loading do detalhe, preview em texto, envio de teste (phone), CRUD de nós e arestas em modais, confirmação de exclusão, validação de JSON (seções/botões), toasts e tratamento de erros da API. Se o fluxo for **Typebot** (`typebot_public_id` preenchido), exibe iframe do Typebot em vez do canvas e oculta a lista "Etapas".
- **Chat**: botão **"Iniciar fluxo"** no menu da conversa (três pontos) chama o endpoint `start-flow`.
- **Rota**: `/configurations/flows`; aba em Configurações.

### Integração
- **Tasks** (`tasks.py`): Mensagens com `metadata.interactive_list` ou `interactive_reply_buttons` são enviadas via Evolution/Meta (lista ou botões).
- **Tenancy**: `allow_meta_interactive_buttons` desativa envio de fluxo (try_send_flow_start e send_test).

---

## Maturidade para produção

| Aspecto | Situação |
|--------|----------|
| **Multi-tenant** | Querysets e perform_create/update filtram por tenant; send_test e flow_engine checam tenant. |
| **Segurança** | IsAdmin; from_node e target_department validados por tenant nas arestas; flow do nó não pode ser alterado na edição. |
| **Idempotência** | `flow_reply_processed` na mensagem; não reenvia start se já existe ConversationFlowState. |
| **Resiliência** | Aresta com to_node removido tratada; option_id normalizado (Evolution); falha ao marcar metadata não quebra o fluxo. |
| **Validação** | Backend: nome, body_text, button_text, sections/rows (id, title), buttons (1–3), to_node mesmo fluxo, destino por target_action. Frontend: JSON e seções com linhas antes de enviar. |
| **UX** | Loading de detalhe, race evitada com ref, ConfirmDialog, Escape nos modais, estados vazios e feedback de erro. |

**Conclusão:** A implementação está **pronta para produção** para o escopo atual (fluxos por Inbox/departamento, lista e botões, coexistência com Welcome Menu), desde que:
- O schema de fluxo (`flow_schema.sql` ou migration 0017) esteja aplicado.
- Tenants e usuários tenham `tenant` definido onde a API assume (comportamento já esperado no resto do app).

---

## O que pode quebrar (e como evitar)

1. **Migration/schema não aplicado**  
   Sem as tabelas `chat_flow`, `chat_flow_node`, `chat_flow_edge`, `chat_conversation_flow_state`, qualquer uso de fluxo falha.  
   **Evitar:** Rodar `flow_schema.sql` ou `python manage.py migrate` (0017) antes de ativar fluxos.

2. **Usuário sem tenant**  
   Se `request.user.tenant` for None, `get_queryset` usa `filter(tenant=None)` (não vaza outros tenants), mas outros pontos podem depender de tenant.  
   **Evitar:** Garantir que usuários que acessam fluxos tenham tenant (já é a regra do app).

3. **Evolution/Meta indisponível**  
   Mensagens de fluxo são enfileiradas; se a task ou a API externa falhar, a mensagem fica pending.  
   **Evitar:** Monitorar fila e status das mensagens; já é comportamento do chat em geral.

4. **Fluxo ativo sem nó inicial**  
   Fluxo sem nós ou sem nó marcado como início: `get_start_node` retorna None, try_send_flow_start e send_test falham com mensagem clara.  
   **Evitar:** Validação no frontend/backend ao desativar o único nó inicial (hoje não há; aceitável como melhoria futura).

5. **Múltiplos nós “início”**  
   Modelo permite; `get_start_node` usa o primeiro com `is_start=True`. Comportamento definido.  
   **Opcional:** Validar no serializer “apenas um is_start por fluxo” para evitar confusão.

6. **Fluxos Typebot**  
   Sem o script SQL dos campos Typebot (`flow_typebot_fields.sql`) ou com a API do Typebot (typebot.io ou URL base self-hosted) inacessível, fluxos Typebot não iniciam e send_test falha.  
   **Evitar:** Aplicar `backend/apps/chat/migrations/flow_typebot_fields.sql` após o schema de fluxo; garantir que a API do Typebot esteja acessível para startChat/continueChat.

---

## Melhorias recomendadas (não bloqueantes)

- **Auditoria / métricas:** Logar ou métrica quando fluxo inicia, avança, transfere ou encerra (para análise e suporte).
- **Limite de nós/arestas por fluxo:** Evitar fluxos gigantes (ex.: máx. 50 nós ou 200 arestas) para não degradar listagem e preview.
- **Validação “um nó inicial”:** No FlowNodeWriteSerializer, ao marcar `is_start=True`, desmarcar outros do mesmo fluxo (ou retornar erro se já houver outro).
- **Testes automatizados:** Testes para flow_engine (get_start_node, process_flow_reply, try_send_flow_start) e para a API (create flow/node/edge, send_test, validações).
- **Frontend:** Suporte a paginação na lista de fluxos se o número de fluxos crescer muito.

---

## Checklist pré-produção

- [ ] Schema de fluxo aplicado (flow_schema.sql ou migrate 0017).
- [ ] Para fluxos Typebot: script `flow_typebot_fields.sql` aplicado; API do Typebot (typebot.io ou self-hosted) acessível.
- [ ] Tenant com `allow_meta_interactive_buttons` configurado conforme desejado.
- [ ] Pelo menos um fluxo com nó inicial e arestas testado (envio + resposta) no ambiente alvo.
- [ ] Verificar que conversas novas/reabertas recebem fluxo ou Welcome Menu conforme esperado.
