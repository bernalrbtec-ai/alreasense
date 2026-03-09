# Maturidade e implantação: fluxos (backend + frontend)

## Escopo do que está pronto para implantar

### Backend

| Componente | Alteração | Impacto |
|------------|-----------|---------|
| **authn 0003** | State: `CreateModel(Department)` via SeparateDatabaseAndState | Apenas estado do Django; banco já era criado pelo RunPython. |
| **chat 0001** | State: `CreateModel(Conversation, Message, MessageAttachment)` via SeparateDatabaseAndState | Apenas estado do Django; tabelas já eram criadas pelo RunSQL. |
| **0017_flow_schema** | RunSQL flow_schema.sql; reverse_sql para rollback das tabelas de fluxo | Cria chat_flow, chat_flow_node, chat_flow_edge, chat_conversation_flow_state. |
| **0018 (opcional)** | Script SQL `docs/sql/chat/0018_flow_node_media_url.up.sql` | Adiciona coluna `media_url` em chat_flow_node se faltar (tipos image/file). |
| **flow_engine.py** | `process_flow_reply`: atomic + lock na mensagem, guards, log para departamento inexistente | Comportamento das transições mantido; menos race e mais robustez. |

### Frontend (canvas + CRUD completo)

| Componente | Situação |
|------------|----------|
| **FlowPage** | Lista fluxos, criar/selecionar, skeleton de loading, empty states. |
| **Editar e excluir fluxo** | Modal editar (nome, escopo, departamento) com PATCH; excluir com confirmação e DELETE; refetch e setSelectedFlow(null) após exclusão. |
| **Edição sem JSON** | Formulários estruturados: lista (até 10 seções, 10 linhas cada), botões (1–3), tipos message/image/file com media_url; validação de ids únicos. |
| **Canvas (React Flow)** | Exibição de nós e arestas; clique no nó abre edição; sincronização por assinatura (não reseta a cada re-render). |
| **UX** | Modais com backdrop blur e animação (framer-motion); transições em listas e cards; ícones por tipo de nó; double submit evitado. |

---

## O que foi verificado

- **Migrations:** Ordem de dependências (authn 0003 → chat 0001 → chat 0017) e referências conferidas; `migrate --plan` executado com sucesso. Script 0018 (media_url) executado com sucesso no ambiente do desenvolvedor.
- **Flow engine:** Lógica de próximo nó, transferir e encerrar revisada; lock com `select_for_update`; idempotência com `flow_reply_processed`; guards; aviso quando departamento da aresta não existe.
- **Frontend:** FlowPage com CRUD de fluxo, canvas (React Flow), edição sem JSON e editar/excluir; double submit e refetch evitados; canvas sincronizado por assinatura.
- **Linter:** Sem erros nos arquivos alterados.
- **Reversão:** Migrations não alteram esquema em ambientes que já tinham as tabelas; flow_engine e frontend só adicionam comportamento (não removem caminhos existentes).

---

## Riscos e mitigações

| Risco | Probabilidade | Mitigação |
|-------|----------------|-----------|
| `migrate` em banco novo falhar por ordem de apps | Baixa | Dependências 0003 → 0001 → 0017 e state_operations conferidos. |
| Processamento duplicado da mesma resposta (lista/botão) | Baixa | Lock na mensagem + `flow_reply_processed`; um worker por mensagem. |
| Aresta para departamento removido | Baixa | Log de warning; estado do fluxo removido; conversa não fica presa. |
| Falha de `state.save()` após envio do nó | Muito baixa | Rollback do atomic; retry pode reenviar uma vez; estado permanece consistente. |

Nenhum risco alto identificado para o escopo atual (migrations + flow engine).

---

## Checklist pré-implantação

- [ ] Backup do banco antes de rodar `migrate` (recomendado em produção).
- [ ] Dependências instaladas (backend e frontend, incl. `@xyflow/react`); `python manage.py check` sem erros.
- [ ] Rodar `python manage.py migrate` (ou `migrate --plan` primeiro); se a tabela `chat_flow_node` foi criada sem `media_url`, executar `docs/sql/chat/0018_flow_node_media_url.up.sql` antes ou após o migrate.
- [ ] Após deploy: testar um fluxo de ponta a ponta: na UI criar/editar fluxo, adicionar nó (lista ou botões), aresta, envio de teste; em conversa real: início, escolher opção, próximo nó ou transferir/encerrar.

---

## Maturidade e recomendação

### Maturidade: **alta para o escopo atual**

- **Migrations:** Ajuste apenas de **estado** (state_operations). Nenhuma mudança de DDL em bancos que já tenham as tabelas; em banco novo, o comportamento é o mesmo de antes, com o estado correto para 0017.
- **Flow engine:** Lógica já existente preservada; melhorias são defensivas (lock, idempotência, guards, log). Compatível com uso atual do fluxo (lista/botões, transferir, encerrar).

### Podemos implantar sem problemas?

**Sim**, para o que foi alterado (migrations + flow_engine), desde que:

1. O ambiente tenha as dependências instaladas e `manage.py check` passe (ou seja usado `--skip-checks` apenas se já for prática do ambiente).
2. Em produção, faça backup do banco antes do `migrate`.
3. Após o deploy, rode um teste rápido de fluxo (início → opção → próximo nó ou transferir/encerrar) para validar em runtime.

**Frontend (canvas + CRUD):** O [Plano de canvas de fluxos](PLANO_CANVAS_FLUXO.md) foi implementado: canvas com React Flow, edição sem JSON e editar/excluir fluxo. A UI está integrada à API existente; sem mudanças destrutivas.

---

## Resumo: pode levar para produção?

**Sim. Está maduro para produção** no escopo atual (fluxos por Inbox/departamento, lista e botões, canvas, edição sem JSON, editar/excluir fluxo), desde que:

1. **Backend:** Migrations aplicadas (0017; 0018 se a tabela foi criada sem `media_url`). Backup do banco antes do `migrate` em produção.
2. **Ambiente:** Dependências instaladas; `manage.py check` sem erros (ou `--skip-checks` se for prática do ambiente).
3. **Pós-deploy:** Teste rápido de ponta a ponta: criar fluxo → adicionar nó (lista ou botões) → aresta → enviar teste; ou conversa real com escolha de opção e próximo nó/transferir/encerrar.

Riscos permanecem **baixos**; mitigações (lock, idempotência, validações, guards) estão em vigor. Melhorias futuras (auditoria, limite de nós, testes automatizados) não bloqueiam o go-live.
