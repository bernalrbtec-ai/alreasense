# Design: Meus LLMs / Agentes por departamento + anexar ao fluxo

## Objetivo

Permitir criar **agentes LLM** (ex.: "Agente Dúvidas Comercial", "Agente Dúvidas Suporte"), cada um com um **RAG específico** (base de conhecimento do departamento). No editor de **fluxo**, poder **escolher um agente** e anexá-lo a um nó (ex.: "resposta automática" ou "atendimento"), de forma que essa etapa use esse LLM + RAG em vez de mensagem estática.

## Estado atual do produto

- **Fluxo** (`apps/chat/models_flow.py`): `Flow`, `FlowNode` (tipos: message, image, file, list, buttons), `FlowEdge` (next, transfer, end). Nós enviam conteúdo fixo (texto, lista, botões) ou mídia.
- **RAG**:
  - `apps/tenancy/rag_sync.py`: perfil da empresa → webhook n8n (chunk único por tenant).
  - `apps/ai/summary_rag.py`: resumos aprovados → n8n (conversation_summary).
  - `apps/ai/models.py`: `AiKnowledgeDocument` (tenant, content, source, tags) – base por tenant.
- **IA/Secretária** (`TenantSecretaryProfile`): um perfil por tenant (form_data, prompt, signature_name), usado pela Bia/secretária no Inbox. Não é “um agente por departamento” nem “anexável ao fluxo”.

## Visão proposta

### 1. Entidade: Agente LLM (Meus LLMs)

- **Nome:** ex. `LLMAgent` ou `DepartmentAgent` (evitar conflito com “Secretary”).
- **Campos sugeridos:**
  - `tenant` (FK)
  - `name` (ex.: "Agente Dúvidas Comercial")
  - `department` (FK, opcional) – vincula o agente a um departamento; o RAG pode ser filtrado por esse departamento.
  - `rag_source` ou `rag_scope`: identificador do “RAG deste agente” (ex.: `department_id`, ou nome de coleção no pgvector).
  - `system_prompt` (texto)
  - `signature_name` (ex.: "Dúvidas Comercial") – nome exibido nas respostas.
  - `model` / `provider` (opcional) – se no futuro houver mais de um provedor.
  - `is_active` (boolean)
- **RAG por agente:**
  - Opção A: documentos em `AiKnowledgeDocument` com `metadata.department_id` (ou `agent_id`); na consulta RAG, filtrar por esse agente/departamento.
  - Opção B: uma “coleção” ou namespace por agente no pgvector (ex.: `tenant_id + agent_id`), e o n8n ou o backend monta a query com esse filtro.
- **API:** CRUD de agentes (lista, criar, editar, desativar), filtro por tenant; listagem para preencher o seletor no fluxo.

### 2. Fluxo: novo tipo de nó “Agente” / “Resposta LLM”

- **FlowNode:** novo `node_type` (ex.: `llm_reply` ou `agent`).
- **Campos no nó (quando tipo = agent):**
  - `agent` (FK para `LLMAgent`, ou UUID). Quando a conversa “entra” nesse nó, em vez de enviar lista/botões, o motor chama o agente (LLM + RAG) e envia a resposta na conversa.
- **Comportamento no motor** (`flow_engine.py`):
  - Em `send_flow_node`: se `node_type == 'agent'`, não enviar lista/botões; marcar a conversa como “aguardando resposta do agente” ou chamar o serviço do agente de forma assíncrona e, ao receber a resposta, enviar a mensagem e (opcionalmente) avançar para o próximo nó ou manter no mesmo nó para nova pergunta.
- **Arestas:** um nó “agente” pode ter arestas “próxima etapa” / “transferir” / “encerrar” como hoje (ex.: após N trocas ou um botão “Falar com humano”).

### 3. Frontend

- **Tela “Meus LLMs” (ou dentro de Configurações):** lista de agentes do tenant, criar/editar (nome, departamento, prompt, nome de exibição, ativar/desativar). Opcional: upload ou link de documentos para o RAG desse agente.
- **Editor de fluxo:** ao adicionar/editar um nó, se o tipo for “Agente” ou “Resposta LLM”, exibir um **seletor** “Usar agente: [dropdown com agentes do tenant]”. Salvar o `agent_id` no nó.

### 4. Melhorias recomendadas (revisão geral)

- **Fluxo (hoje):**
  - Validar “apenas um nó inicial” por fluxo no backend (evitar múltiplos `is_start`).
  - Limite de nós/arestas por fluxo (ex.: 50 nós) para não degradar listagem.
  - Auditoria/métricas: log quando fluxo inicia, avança, transfere (já sugerido em FLOW_OVERVIEW.md).
- **Grupos (trabalho recente):**
  - Listagem por tenant (todas as instâncias); botão “Sincronizar” só no estado vazio; exclude com `__contains` para `instance_removed`; logs de diagnóstico. Manter esse comportamento.
- **RAG:**
  - Hoje: RAG por tenant (empresa, resumos). Para agentes: evoluir para RAG “por agente” ou “por departamento” (metadado em documentos ou coleção separada).
- **Secretária vs Agentes:**
  - Manter `TenantSecretaryProfile` para o comportamento global da Bia no Inbox.
  - Agentes LLM = entidades separadas, reutilizáveis em fluxos e (futuro) em outros pontos (ex.: aba “Nós”).

### 5. Ordem de implementação sugerida

1. **Modelo e API de Agente LLM** – criar modelo, migration, CRUD (lista/criar/editar), filtro por tenant.
2. **RAG por agente** – definir como os documentos ou o pgvector são filtrados por agente/departamento; ajustar n8n ou backend que consulta RAG.
3. **Fluxo: tipo de nó “Agente”** – novo `node_type`, FK para agente no `FlowNode`, ajustes no `flow_engine` para executar o agente nesse nó.
4. **Frontend: Meus LLMs** – tela de listagem/cadastro de agentes.
5. **Frontend: seletor no fluxo** – ao editar nó tipo “Agente”, dropdown de agentes e persistir `agent_id`.

---

## Resumo

- **Criar meus LLMs:** cadastro de agentes (nome, departamento, prompt, RAG específico).
- **Ex.: “Agente Dúvidas XXXX”:** puxar esse agente e anexar no fluxo = escolher um nó do tipo “Agente” e selecionar esse agente; a etapa passa a usar esse LLM + RAG naquela parte do fluxo.
- Revisão: manter melhorias já feitas (fluxo, grupos, exclude JSONField); evoluir RAG e fluxo para suportar “nó agente” e “Meus LLMs” de forma incremental.
