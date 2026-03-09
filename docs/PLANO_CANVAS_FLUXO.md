# Plano: Canvas de fluxos (edição visual + sem JSON)

Este é o **único plano de escopo** para a evolução da funcionalidade de fluxos no Sense. Define a entrega do canvas (editor visual estilo React Flow/Typebot), edição sem JSON e editar/excluir fluxo.

**Referências:** Backend e API atuais em [FLOW_OVERVIEW.md](FLOW_OVERVIEW.md). Migrations e flow engine em [REVISAO_FLUXO_E_MIGRATIONS.md](REVISAO_FLUXO_E_MIGRATIONS.md).

---

## Escopo da entrega

- **Canvas:** Editor visual de fluxos (nós e arestas), estilo React Flow / Typebot, em uma única entrega com a edição sem JSON.
- **Edição sem JSON:** Configurar lista (seções/linhas) e botões por formulário (não editar JSON bruto); limites: até 10 seções, 10 linhas por seção; botões 1–3; suporte a message/image/file conforme tipo de nó.
- **Editar e excluir fluxo:** PATCH para nome, escopo e departamento; DELETE com confirmação; após sucesso chamar `fetchFlows()` e `setSelectedFlow(null)`.

---

## Canvas (editor visual)

- Biblioteca sugerida: **React Flow** (ou equivalente) para desenhar nós e conexões.
- Nós representam os FlowNodes (lista ou botões); arestas representam FlowEdges (option_id → próximo nó, transferir ou encerrar).
- Interações: arrastar nós, conectar opções a destinos, selecionar nó para editar corpo/seções/botões no painel lateral (edição sem JSON).
- Persistência: alterações salvas via API existente (PATCH/POST de nodes e edges).

---

## Edição sem JSON

- **Lista (node_type list):** Formulário com seções; cada seção tem título e linhas (id, title, description). Limites: 10 seções, 10 linhas por seção. Validação e parsing seguro de dados existentes (evitar quebra com JSON malformado).
- **Botões (node_type buttons):** Até 3 botões; cada um com id e title. Validação de ids únicos.
- **Tipos de conteúdo:** message (texto), image, file conforme definido no modelo/nó.
- **Nó inicial:** Apenas um `is_start=True` por fluxo; ao marcar outro, desmarcar o anterior ou validar no backend.

---

## Edição e exclusão do fluxo

- **Editar fluxo (nome, escopo, departamento):**  
  `PATCH /chat/flows/${id}/` com payload permitido; após sucesso, refetch do fluxo selecionado (ou lista) e atualizar UI.
- **Excluir fluxo:**  
  `DELETE /chat/flows/${id}/` com confirmação (modal). Após sucesso: `fetchFlows()` e `setSelectedFlow(null)`.
- Garantir que os endpoints existentes (`api.patch(\`/chat/flows/${id}/\`, ...)` e `api.delete(\`/chat/flows/${id}/\`)`) são usados com URLs corretas (barra final no path).

---

## Transferências entre nós (motor já implementado)

- O backend (`flow_engine.process_flow_reply`) já processa três transições: **próximo nó** (to_node), **transferir** (target_department_id), **encerrar** (target_action end).
- Usa lock na mensagem e `flow_reply_processed` para idempotência; `option_id` normalizado para match com list_reply/button_reply da Evolution/Meta.
- No frontend/canvas: ao criar ou editar arestas, garantir que o `option_id` enviado corresponde ao id da linha (lista) ou do botão, para o motor resolver corretamente.

---

## Edge cases a tratar

- Carregamento: estados de loading ao buscar fluxo e nós/arestas; não abrir canvas com dados incompletos.
- Vazios: fluxo sem nós; fluxo sem nó inicial; lista sem seções/linhas; botões vazios — UI clara e validação antes de salvar.
- Erros de API: toasts e mensagens de erro; não deixar formulário em estado inconsistente.
- Regras de negócio: unique_together (flow, name) no nó; (from_node, option_id) na aresta; apenas um is_start por fluxo; option_id obrigatório nas arestas.
- Formulários: trim no nome do fluxo; evitar double submit; ao excluir nó/aresta, confirmar e atualizar lista/canvas.
- Canvas: arestas órfãs (to_node removido) — backend já trata; no frontend, ao excluir nó, remover ou desvincular arestas que apontam para ele.
- Acessibilidade: foco em modais, Escape para fechar, labels em campos.
- Tabela de limites: documentar ou exibir na UI os limites (seções/linhas/botões) para o usuário.

---

## Problemas a evitar

- Refetch: após editar fluxo (PATCH flow), recarregar o fluxo selecionado para refletir nome/escopo/departamento.
- Tipo de nó: ao mudar node_type (list ↔ buttons), validar e limpar/ajustar sections ou buttons para não enviar dados inválidos.
- Nó inicial: não permitir remover o único nó inicial sem definir outro, ou exibir aviso.
- Ids únicos na lista: cada row deve ter id único; validar no frontend e backend.
- Arestas órfãs: ao deletar nó, remover arestas que referenciam esse nó (ou impedir exclusão enquanto houver arestas apontando).
- Nome do fluxo: aplicar trim antes de enviar ao backend.
- Departamentos: ao abrir modal de transferência (target_department), carregar lista de departamentos do tenant.
- Double submit: desabilitar botão de submit ou usar flag para não enviar duas vezes.
- Exclusões: confirmação antes de excluir fluxo, nó ou aresta; mensagem clara do que será removido.
- Layout e dados inválidos: validar JSON de sections/buttons ao carregar dados existentes; não quebrar a UI com dados malformados.

---

## Ordem sugerida de implementação

1. Edição e exclusão do fluxo (PATCH/DELETE + UI) para estabilizar CRUD completo.
2. Formulários de edição sem JSON para lista e botões (substituir ou complementar edição por JSON).
3. Canvas com React Flow: exibir nós e arestas; editar nó no painel (reutilizando formulários sem JSON); criar/editar arestas (option_id → próximo nó / transferir / encerrar).
4. Ajustes de edge cases e problemas a evitar (validações, refetch, acessibilidade).

---

## Migration / SQL para o canvas

Se a tabela `chat_flow_node` foi criada pela migration 0017 (`flow_schema.sql`) **sem** a coluna `media_url`, rode o script abaixo antes de usar os tipos de nó **Imagem** e **Arquivo** no canvas:

- **[docs/sql/chat/0018_flow_node_media_url.up.sql](sql/chat/0018_flow_node_media_url.up.sql)** — adiciona `media_url VARCHAR(1024)` de forma idempotente.

Em bancos que já usam `flow_schema_complete.sql` ou que já têm a coluna, o script é seguro (ADD COLUMN IF NOT EXISTS).

---

## Nota sobre cancelamento de migrations

O projeto **não utiliza** o plano de cancelamento de migrations em produção. Os scripts em `docs/sql/` servem para **auditoria e provisionamento** de banco; a estratégia de “cancelar” migrations está documentada em [CANCELAMENTO_MIGRATIONS_PRODUCAO.md](CANCELAMENTO_MIGRATIONS_PRODUCAO.md) apenas como referência histórica, fora de uso.
