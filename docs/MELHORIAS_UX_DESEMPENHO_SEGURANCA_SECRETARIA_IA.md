# Melhorias: UX, Desempenho e Segurança (Projeto + Plano Secretária IA)

**Contexto:** Leitura do projeto Sense e do plano [secretária_ia_e_agentes_por_departamento](.cursor/plans/secretária_ia_e_agentes_por_departamento_7fc937bc.plan.md). Este documento lista o que pode ser melhorado em **UX**, **desempenho** e **segurança**, tanto no estado atual do produto quanto na implementação futura da Secretária IA e agentes por departamento.

---

## 1. UX

### 1.1 Secretária IA (quando implementada)

- **Formulário “Dados da empresa”**
  - **Wizard em etapas:** Dividir em 2–3 etapas (ex.: “Empresa” → “Departamentos e palavras-chave” → “Revisão”) para não sobrecarregar.
  - **Preview do contexto RAG:** Após salvar, mostrar um resumo do texto que será usado como contexto (ex.: “Este texto será usado para as respostas da secretária”) para o usuário validar.
  - **Feedback ao ativar:** Ao marcar “Ativar secretária no Inbox”, mostrar mensagem clara: “A secretária responderá automaticamente em conversas do Inbox com base nos dados cadastrados.”

- **Inbox e encaminhamento**
  - **Indicador visual de “respondido pela IA”:** Nas mensagens da secretária, exibir um badge/ícone (ex.: “Secretária IA”) para o agente saber que foi resposta automática.
  - **Resumo para o departamento em destaque:** Ao encaminhar, exibir o `summary_for_department` numa nota interna ou card visível na conversa, para o agente humano continuar o atendimento sem reler tudo.
  - **Confirmação antes de atribuir ao departamento:** Opção (configurável) de “Confirmar encaminhamento” antes de mudar `conversation.department` e `status`, para evitar encaminhamentos errados.

- **Memória (1 ano por contato)**
  - **Transparência:** Em Configurações > IA, seção “Memória da secretária” com texto: “A secretária lembra do histórico com cada cliente nos últimos 12 meses, apenas dentro da sua empresa.”
  - **Privacidade/ LGPD:** Opção de “Não usar memória de conversas anteriores” (desativa `search_memory_for_contact` para esse tenant).

### 1.2 Chat e Inbox (atual)

- **DepartmentTabs / Inbox**
  - **Contador de pendentes no Inbox:** Já existe lógica por `status === 'pending'` e `!conv.department`; garantir que o backend envie `pending_count` para o “Inbox” (conversas sem departamento) no mesmo formato dos departamentos, para o badge ficar consistente.
  - **Empty state no Inbox:** Quando não houver conversas pendentes no Inbox, mensagem amigável: “Nenhuma conversa aguardando. Novas conversas sem departamento aparecerão aqui.”

- **Configurações (ConfigurationsPage)**
  - **Seção “Secretária IA” (futura):** Agrupar em um card “Secretária IA” com: link para “Dados da empresa”, toggle “Ativar no Inbox” e link para “Horários de atendimento” (se a secretária respeitar business hours no futuro).
  - **Agentes por departamento (futuro):** Na tela de edição de departamento, campo “Agente IA (opcional)” com lista de agentes do tenant, conforme [PLANEJAMENTO_AGENTE_IA_DEPARTAMENTO.md](PLANEJAMENTO_AGENTE_IA_DEPARTAMENTO.md).

### 1.3 Navegação e roles

- **Agente (role agente):** Já redireciona para `/chat` e tem acesso a Chat, Agenda, Contatos, Perfil. Revisar se “Contatos” para agente mostra apenas o necessário (ex.: sem ações de importação em massa).
- **Feedback de loading:** Em ações que chamam gateway IA (teste de triagem, gateway reply), manter toasts de “Processando…” e “Sucesso/Erro” para não parecer travado.

---

## 2. Desempenho

### 2.1 Backend

- **RAG e memória (Secretária IA)**
  - **Filtro por `source='secretary'` em `search_knowledge`:** Ao implementar o plano, na chamada para a secretária passar `source='secretary'` (ou filtro equivalente) para não varrer documentos de outros contextos. Se o `vector_store` não suportar filtro por `source`, adicionar parâmetro opcional e índice em `(tenant_id, source)`.
  - **`search_memory_for_contact`:** Implementar conforme plano (por `tenant_id` + `contact_phone` + janela 365 dias). Usar índice em `(tenant_id, conversation_id)` e garantir que a lista de `conversation_id` seja obtida com uma query eficiente (ex.: `Conversation.objects.filter(tenant_id=..., contact_phone=...).values_list('id', flat=True)`).
  - **Embedding do contexto da secretária:** Gerar embedding ao salvar o perfil (ou ao ativar); não na hora da mensagem. Assim a latência do Inbox fica menor.

- **Webhook Evolution**
  - **Ponto de integração Secretária:** Ao adicionar o fluxo “se Inbox e secretary_enabled → chamar IA”, fazer a chamada à IA de forma **assíncrona** (task em background, ex.: Celery ou thread como no triage), para o webhook responder 200 rápido e não estourar timeout da Evolution.
  - **Evitar N+1:** No webhook, onde já existe `select_related('tenant', 'default_department')` em `WhatsAppInstance`, manter e estender para qualquer novo relacionamento usado no fluxo da secretária (ex.: `TenantAiSettings`, `TenantSecretaryProfile`).

- **Queries e índices**
  - **AiMemoryItem:** Índice composto `(tenant_id, conversation_id, created_at)` para a busca por contato (conversas do contato + `created_at >= now() - 365 days`).
  - **AiKnowledgeDocument:** Índice `(tenant_id, source)` para filtrar `source='secretary'` sem full scan.
  - **Paginação:** Garantir que listagens (ex.: triage history, gateway audit) usem `LimitOffsetPagination` ou equivalente; já existe em vários endpoints, revisar os que ainda retornam listas grandes sem limite.

### 2.2 Frontend

- **Dashboard:** O polling de 30s já está condicionado a “WebSocket desconectado” ([DashboardPage.tsx](../frontend/src/pages/DashboardPage.tsx)), o que está alinhado com a análise de performance. Manter e evitar novos pollings desnecessários.
- **Chat:** Manter lazy load e uso do WebSocket para mensagens; ao exibir “resumo para departamento” da secretária, renderizar em bloco colapsável para não aumentar muito o DOM.
- **Configurações:** A página é pesada; manter lazy load e, na seção futura “Secretária IA”, carregar dados do perfil (form_data) sob demanda (ex.: ao abrir o card), não tudo no mount.

### 2.3 Gateway IA (n8n)

- **Contrato da Secretária:** Incluir no payload para o n8n um campo que identifique o “agente” como `secretary` (ex.: `agent_type: 'secretary'`) e, na resposta, `suggested_department_id` e `summary_for_department` para o backend executar o encaminhamento em uma única ida ao n8n (evitar segunda chamada só para encaminhar).
- **Timeout e retry:** Definir timeout adequado (ex.: 15–20s) e política de retry (ex.: 1 retry com backoff) para não travar o fluxo do Inbox em caso de lentidão do modelo.

---

## 3. Segurança

### 3.1 Crítico (já documentado em ANALISE_SEGURANCA_COMPLETA.md)

- **API key Evolution em plaintext:** Não retornar `api_key` completa no GET/POST de conexão. Retornar mascarada (ex.: `****...últimos4`) e usar campo tipo senha no frontend. Persistir apenas valor criptografado no backend.
- **Credenciais em defaults (settings.py):** Remover defaults com valores reais para S3, RabbitMQ, Evolution. Usar `default=''` ou falhar explícito em produção se variável não estiver definida.
- **CORS:** Trocar `CORS_ALLOW_ALL_ORIGINS = True` por lista explícita de origens permitidas (ex.: `CORS_ALLOWED_ORIGINS` com o domínio do frontend).

### 3.2 Secretária IA e agentes (ao implementar)

- **Isolamento por tenant:**
  - `TenantSecretaryProfile`: sempre filtrado por `tenant_id` do usuário autenticado; API GET/PUT apenas para o próprio tenant.
  - RAG e memória: `search_knowledge` e `search_memory_for_contact` já recebem `tenant_id`; garantir que esse `tenant_id` venha do objeto da conversa/mensagem (nunca do body da requisição).
- **Webhook Evolution (AllowAny):** O webhook que recebe mensagens é `AllowAny`. O fluxo da secretária roda no backend após identificar o tenant pela instância (WhatsAppInstance → tenant). Não expor dados de outros tenants no payload enviado ao n8n; enviar apenas `tenant_id`, `conversation_id`, `message_id`, texto necessário e contexto RAG/memória já filtrados por tenant (e por contato na memória).
- **Dados sensíveis no contexto RAG:** O texto montado do formulário (missão, endereço, telefone, etc.) será enviado ao gateway. Garantir que o canal com n8n seja HTTPS e que o n8n não logue o corpo completo em claro. No backend, não logar o conteúdo completo do contexto em nível INFO.
- **Auditoria:** Registrar em `AiGatewayAudit` (ou equivalente) as chamadas da secretária (conversation_id, tenant, latency, handoff, suggested_department_id) sem guardar o texto completo da mensagem do cliente no audit (apenas resumo ou hash se necessário para suporte).

### 3.3 Geral

- **Rate limiting:** Manter throttle no gateway (ex.: `GatewayReplyThrottle`) e considerar rate limit por tenant para o endpoint de “resposta da secretária” (n8n → backend), para evitar abuso.
- **Validação de entrada:** No PUT do perfil da secretária, validar e sanitizar `form_data` (tamanho máximo, tipos de campo, sem scripts); idem para `routing_keywords` em departamentos (lista de strings com tamanho limitado).

---

## 4. Resumo de prioridades

| Área        | Prioridade | Ação resumida |
|------------|------------|----------------|
| Segurança  | Alta       | Deixar de retornar API key em plaintext; remover defaults com credenciais; restringir CORS. |
| Desempenho | Média      | Secretária: RAG/memória com filtros e índices; chamada IA assíncrona no webhook; contrato n8n com suggested_department + summary. |
| UX         | Média      | Formulário em etapas + preview do contexto; indicador “Secretária IA” na mensagem; resumo para departamento visível no chat; empty state no Inbox. |
| Segurança (Secretária) | Média | Isolamento tenant em perfil e RAG; não logar contexto completo; auditoria sem conteúdo bruto. |

---

## 5. Referências no código

- Plano: [secretária_ia_e_agentes_por_departamento_7fc937bc.plan.md](../.cursor/plans/secretária_ia_e_agentes_por_departamento_7fc937bc.plan.md)
- Agentes por departamento: [PLANEJAMENTO_AGENTE_IA_DEPARTAMENTO.md](PLANEJAMENTO_AGENTE_IA_DEPARTAMENTO.md)
- Modelos IA: [backend/apps/ai/models.py](../backend/apps/ai/models.py) (`TenantAiSettings`, `AiKnowledgeDocument`, `AiMemoryItem`)
- Vector store: [backend/apps/ai/vector_store.py](../backend/apps/ai/vector_store.py) (`search_knowledge`, `search_memory` – hoje sem filtro por contato)
- Webhook e Inbox: [backend/apps/chat/webhooks.py](../backend/apps/chat/webhooks.py) (evolution_webhook; conversa com `department=None` e `status='pending'` = Inbox)
- Gateway e triagem: [backend/apps/ai/views.py](../backend/apps/ai/views.py) (gateway_reply, triage); [backend/apps/ai/triage_service.py](../backend/apps/ai/triage_service.py) (contexto RAG + memória)
- Segurança: [ANALISE_SEGURANCA_COMPLETA.md](../ANALISE_SEGURANCA_COMPLETA.md)
- Performance: [ANALISE_PERFORMANCE_COMPLETA.md](../ANALISE_PERFORMANCE_COMPLETA.md)
