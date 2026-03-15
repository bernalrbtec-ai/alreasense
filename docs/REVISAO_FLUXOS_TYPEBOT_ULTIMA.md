# Última revisão: Fluxos Typebot e controles

Documento de revisão detalhada do que foi implementado (fluxos, Typebot, parar fluxo, modal e edge cases).

---

## 1. Backend

### 1.1 Modelo Flow (`models_flow.py`)
- **Campo `description`**: `CharField(max_length=500, blank=True, default="")`. Usado no modal "Iniciar fluxo" e no formulário de edição.

### 1.2 Motor de fluxo (`flow_engine.py`)
- **`get_active_flow_for_conversation(conversation)`**: Retorna o primeiro fluxo ativo do escopo (Inbox ou departamento). Usa `get_active_flows_for_conversation(conversation).first()`.
- **`get_active_flows_for_conversation(conversation)`**: Retorna queryset de fluxos ativos (tenant + escopo). Retorna `Flow.objects.none()` se sem conversa ou sem tenant.
- **`try_send_flow_start(conversation, flow=None)`**: 
  - Se `flow` for passado, valida com `get_active_flows_for_conversation(conversation).filter(id=flow.id).exists()`; se inválido, usa o primeiro do escopo.
  - Respeita `allow_meta_interactive_buttons` do tenant.
  - Não inicia se já existir `ConversationFlowState` para a conversa.
- **`process_incoming_message_flows(conversation, message)`**:
  - Retorna `False` se conversa sem humano (`assigned_to_id`), sem mensagem ou **conversa fechada** (`status == "closed"`).
  - Ordem: Typebot (continueChat) → fluxo Sense (lista/botão) → menu de boas-vindas.
  - Usado pelo webhook Evolution e pelo **webhook Meta** (Cloud API).

### 1.3 Typebot (`typebot_flow_service.py`)
- **start_typebot_flow**: Prefilled com variáveis da conversa + Contact (NomeContato, NumeroFone, email). `textBubbleContentFormat: "markdown"`. Persiste `session_id` e `resultId` em estado; garante `state.metadata` antes de escrever.
- **continue_typebot_flow**: Payload com `"text"` (não `"content"`). Em 404/410 limpa `typebot_session_id` e retorna `False`. Extração de texto aceita `data` não-dict (retorna `[]`). **Defensivo:** `flow = getattr(state, "flow", None)` e retorna `False` se flow ausente.
- **Extração de texto**: Suporta `content` string, `content.type === "markdown"`, `content.richText` (recursivo em `text`/`content`/`children`).

### 1.4 API (`views.py`)
- **`GET /chat/conversations/{id}/flows/`** (`list_flows_for_conversation`): Retorna `[]` para conversas em **grupo**. Para individuais, retorna lista serializada (FlowListSerializer com id, name, description, etc.).
- **`POST /chat/conversations/{id}/start-flow/`** (`start_flow`):
  - Body: `request.data` tratado como dict (fallback `{}`).
  - `flow_id` opcional; se enviado, **validado como UUID** (ValueError/TypeError → 400 "flow_id inválido.").
  - Fluxo deve pertencer ao escopo da conversa (`get_active_flows_for_conversation`).
  - Remove estado existente e chama `try_send_flow_start(conversation, flow=flow)`.
  - Resposta inclui `messages_queued` quando Typebot retorna.

### 1.5 Onde o fluxo é interrompido (estado apagado)
- **Humano assume:** `ConversationFlowState.objects.filter(conversation_id=...).delete()` em:
  - take_conversation (Inbox),
  - start_conversation (atribuir ao usuário),
  - transfer (quando há `assigned_to_id`).
- **Conversa encerrada:**
  - `views.py` close_conversation (endpoint fechar conversa),
  - `welcome_menu_service._close_conversation`,
  - `close_inbox_idle_conversations` (management command).

### 1.6 Webhook Meta (`meta_webhook.py`)
- Após criar a mensagem incoming, chama `process_incoming_message_flows(conversation, new_msg)` dentro de try/except. Assim, mensagens recebidas pela Meta Cloud API disparam Typebot/flow/menu igual ao Evolution.

### 1.7 Serializers (`serializers_flow.py`)
- **FlowSerializer** e **FlowListSerializer**: Incluem `"description"` nos fields. Permite leitura e escrita (PATCH) de descrição.

---

## 2. Frontend

### 2.1 Modal "Iniciar fluxo" (`ChatWindow.tsx`)
- **Abertura:** Botão "Iniciar fluxo" no menu (apenas conversas não-grupo e com `conversationId`).
- **Carregamento:** `GET /chat/conversations/{id}/flows/` ao abrir; resposta tratada como array ou `res.data.results`; itens normalizados com `id`/`name`/`description` em string; itens sem `id` filtrados.
- **Cancelamento:** Flag `cancelled` no useEffect; ao fechar o modal não aplica setState da requisição. Listener em `document` para **Escape** fechar o modal.
- **Lista:** Radio por fluxo; nome + descrição (se houver). Um fluxo: seleção automática. Vários: usuário escolhe.
- **Confirmar:** Envia `flow_id: String(flowId)`; desabilitado se loading, sem fluxos ou (vários fluxos e nenhum selecionado). Toasts para sucesso, 0 mensagens Typebot e erro; erro usa `message` ou `detail` do response e evita mostrar objeto.
- **Estados:** `showStartFlowModal`, `flowsForStart`, `selectedFlowId`, `loadingFlows`, `startFlowLoading`.

### 2.2 FlowPage (`FlowPage.tsx`)
- **Interface Flow:** Inclui `description?: string | null`.
- **Editar fluxo:** Campo "Descrição breve (opcional)" com `editFlowDescription`; em `openEditFlow` preenche com `selectedFlow.description ?? ''`.
- **Salvar:** PATCH envia `description: (editFlowDescription || '').trim()` (nunca `null`, compatível com CharField). Após salvar, `setSelectedFlow` com `description` sempre string (evita null no estado).

---

## 3. Banco de dados (SQL)

- **flow_schema_complete.sql**: Bloco idempotente adiciona `description VARCHAR(500) NOT NULL DEFAULT ''` em `chat_flow` (antes dos campos Typebot).
- **flow_typebot_fields.sql**: Mesmo bloco para `description` para quem aplica só esse script.

**Importante:** Rodar o SQL que adiciona `description` (ou o schema completo) antes ou junto do deploy do código que usa o campo.

---

## 4. Documentação

- **FLUXOS_TYPEBOT_GUIA.md**: 
  - "Quando o fluxo dispara" inclui o modal com lista e confirmação.
  - Nova seção "Quando o fluxo é interrompido" (humano assume; conversa encerrada).
  - "Como configurar" inclui Descrição breve e numeração ajustada.

---

## 5. Edge cases cobertos

| Caso | Tratamento |
|------|------------|
| Request body não é dict | `data = request.data if isinstance(request.data, dict) else {}` |
| flow_id não é UUID | `UUID(flow_id)` + except → 400 |
| Conversa em grupo em list_flows | Retorna `[]` |
| Modal fechado antes do fetch terminar | `cancelled = true` no cleanup do useEffect |
| Resposta da API com results em vez de array | `res.data.results` quando existir |
| Fluxos sem id ou com nome/description não string | Normalização e `.filter(f => f.id)` |
| Conversa fechada e mensagem chegando | `process_incoming_message_flows` retorna False se `status == "closed"` |
| state.metadata None no start Typebot | `if state.metadata is None: state.metadata = {}` |
| Sessão Typebot 404/410 | Limpa `typebot_session_id` e retorna False |
| Resposta continueChat não-dict | `_extract_text_from_messages(data) if isinstance(data, dict) else []` |
| state.flow ausente (FK) | `getattr(state, "flow", None)` e retorno False |
| description null no PATCH Flow | Frontend envia string vazia, não null |
| Erro de API no start-flow (frontend) | Toast com `message` ou `detail` em string |

---

## 6. Checklist pré-deploy

- [ ] SQL aplicado: coluna `description` em `chat_flow` (flow_schema_complete.sql ou flow_typebot_fields.sql).
- [ ] Backend: sem erros de import ou modelo (Flow.description existe).
- [ ] Frontend: modal "Iniciar fluxo" só para conversas não-grupo; listagem e confirmação ok.
- [ ] Testes manuais: iniciar fluxo (um e vários), fechar conversa, assumir conversa, enviar mensagem com fluxo ativo (Evolution e Meta se aplicável).

---

*Revisão gerada após implementação dos controles de parar fluxo (humano/conversa encerrada), modal com lista e descrição, e endurecimento de edge cases.*
