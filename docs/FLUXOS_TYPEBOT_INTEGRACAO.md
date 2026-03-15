# Fluxos: estado atual e integração com Typebot

## 1. O que já existe (Sense – fluxo próprio)

### Modelos (`apps/chat/models_flow.py`)
- **Flow**: tenant, nome, escopo (`inbox` | `department`), department (opcional), whatsapp_instance, is_active.
- **FlowNode**: etapas do tipo mensagem, lista, botões, imagem, arquivo, timer (delay). Cada nó tem sections/buttons e posição no canvas.
- **FlowEdge**: opção (rowId/button id) → próxima etapa, transferência para departamento ou encerrar.
- **ConversationFlowState**: conversa ↔ fluxo + nó atual.

### Quando o fluxo é disparado
- **Nova conversa** (primeira mensagem incoming): após criar/atualizar a conversa no webhook, chama `try_send_flow_start(conversation)`. Se existir fluxo ativo para o escopo (Inbox ou departamento da conversa), envia o nó inicial (lista/botões/mensagem) via WhatsApp.
- **Conversa reaberta** (estava fechada e chega nova mensagem): mesmo `try_send_flow_start`; se houver fluxo para o escopo, envia o início do fluxo.
- **Resposta do usuário**: quando a conversa está em um fluxo (`ConversationFlowState`), `process_flow_reply` trata lista/botão e avança para o próximo nó, transfere para departamento ou encerra.

### O que também dispara fluxo (já implementado)
- **Transferência manual** (agente transfere conversa para outro departamento): após mudar o departamento, o endpoint de transferência chama `try_send_flow_start(conversation)`. Se o novo departamento tiver fluxo ativo (Sense ou Typebot), o fluxo inicia.
- **Ativar fluxo no meio da conversa**: o botão **"Iniciar fluxo"** no menu da conversa (três pontos) chama o endpoint `POST /chat/conversations/{id}/start-flow/`, que reinicia o fluxo do escopo atual (Inbox ou departamento).

### Frontend
- **FlowPage**: lista de fluxos, CRUD, canvas (React Flow) para editar nós e arestas, envio de teste para um número.
- **FlowCanvas**: arrastar nós (mensagem, lista, botões, etc.), conectar por opção, salvar posição.

---

## 2. Typebot: integração em tela e por tenant

### Iframe do Typebot
- No Typebot, aba **Share** → **Iframe**: gera uma URL para embed (ex.: `https://typebot.io/embed/xxx` ou self-hosted `https://seu-typebot.com/embed/xxx`).
- Dá para passar **variáveis pré-preenchidas** na URL ou no init (ex.: `prefilledVariables: { tenantId, conversationId, contactPhone }`).
- **Separar por tenant**: cada tenant pode ter um ou mais typebots. No Sense, o mapeamento seria: **Flow** (por escopo Inbox/departamento) → **typebot public ID** (ou URL do embed). Assim, por tenant você tem vários Fluxos (Sense), cada um podendo apontar para um Typebot diferente (incluindo um typebot “por departamento” ou “por tipo de atendimento”).

### API do Typebot (execução headless)
- **Iniciar sessão**: `POST /api/v1/typebots/{publicId}/startChat` (produção) ou `.../preview/startChat` (teste). Body pode ter `prefilledVariables: { "Nome": "João", "tenant_id": "..." }`.
- **Continuar**: `POST /api/v1/sessions/{sessionId}/continueChat` com `{ "message": "resposta do usuário" }`.
- Resposta traz mensagens do bot; para integrar ao WhatsApp é preciso **enviar essas mensagens pela nossa stack** (Evolution/Meta) e **receber as respostas do usuário** (webhook) e repassar ao Typebot (`continueChat`).

Conclusão: **sim, dá para integrar**; **sim, dá para separar por tenant** (cada Flow do tenant pode ter um `typebot_public_id` ou URL própria). O iframe serve para **edição/visualização** do fluxo no Sense; a **execução** no WhatsApp exige ponte backend (Sense ↔ Typebot API + webhook).

---

## 3. Implementação realizada

O que existe no código hoje:

### Modelos (`backend/apps/chat/models_flow.py`)
- **Flow**: `typebot_public_id`, `typebot_base_url` (opcionais). Quando `typebot_public_id` está preenchido, o fluxo é executado pelo Typebot em vez de nós/arestas.
- **ConversationFlowState**: `typebot_session_id` (sessão retornada pelo startChat); `current_node` é nullable quando o fluxo é Typebot.

### Schema (script SQL)
- **Script** `backend/apps/chat/migrations/flow_typebot_fields.sql`: adiciona as colunas Typebot em `chat_flow` e `chat_conversation_flow_state`, torna `current_node_id` nullable e cria índice em `typebot_session_id`. Idempotente. Aplicar manualmente após `flow_schema.sql` (ou migration 0017).

### Serviço (`backend/apps/chat/services/typebot_flow_service.py`)
- **start_typebot_flow**: chama startChat na API do Typebot, persiste `session_id` no ConversationFlowState, envia as mensagens da resposta ao WhatsApp.
- **continue_typebot_flow**: chama continueChat com a mensagem do usuário e envia as mensagens de resposta ao WhatsApp.
- **URL base**: `_typebot_base_url(flow)` — vazio = `https://typebot.io/api/v1`; self-hosted = URL informada (com ou sem `/api/v1`, o código normaliza).
- As mensagens enviadas ao WhatsApp vêm do **body da resposta** da API (startChat/continueChat); **não é usado webhook do Typebot** para enviar ao WhatsApp.
- Funções auxiliares: `_extract_text_from_messages` (tipo text/richText), `_send_texts_to_whatsapp` (Message + send_message_to_evolution).

### Integração no motor (`backend/apps/chat/services/flow_engine.py`)
- Em **try_send_flow_start**: se `flow.typebot_public_id` estiver preenchido, chama `start_typebot_flow(conversation, flow)` e retorna; senão segue a lógica com nós/arestas.

### Webhook (`backend/apps/chat/webhooks.py`)
- Antes de `process_flow_reply`: se a conversa tem estado com `typebot_session_id`, chama `continue_typebot_flow(conversation, message.content)`; senão chama `process_flow_reply`.

### API
- **views.py** (ConversationViewSet): `POST /chat/conversations/{id}/start-flow/` reinicia o fluxo (remove estado e chama `try_send_flow_start`). No **transfer**, após mudar o departamento, chama `try_send_flow_start`.
- **views_flow.py**: `send_test` para fluxo Typebot usa `start_typebot_flow` (e exige conversa existente com o número).
- **serializers_flow.py**: expõem `typebot_public_id` e `typebot_base_url` no CRUD de fluxos.

### Frontend
- **FlowPage** (`frontend/src/pages/FlowPage.tsx`): modal "Editar fluxo" com campos Typebot Public ID e URL base. Quando `flowDetail.typebot_public_id` existe, exibe iframe do Typebot (`{viewerBase}/embed/{publicId}`) em vez do canvas e oculta a lista "Etapas".
- **ChatWindow** (`frontend/src/modules/chat/components/ChatWindow.tsx`): botão "Iniciar fluxo" no menu da conversa (três pontos), que chama o endpoint `start-flow`.

### Alinhamento com cadastro de contato
- **Ao iniciar o fluxo (startChat)**: o Sense busca um **Contact** pelo tenant e pelo telefone normalizado da conversa. Se existir, envia nas variáveis pré-preenchidas: `NomeContato`, `NumeroFone`, `number`, `pushName` e `email` (quando o contato tiver email). Assim o Typebot já recebe nome, telefone e email quando o contato estiver cadastrado.
- **No webhook do Typebot** (`POST /api/chat/webhooks/typebot/`): após salvar as variáveis em `ConversationFlowState` e `Conversation.metadata`, o Sense atualiza ou cria o **Contact** com os dados enviados pelo Typebot. Variáveis reconhecidas: `NomeContato`, `name`, `nome` → nome do contato; `email` → email; `NumeroFone`, `number` → telefone. Se o contato já existir (tenant + telefone), é atualizado; se não existir e houver telefone na conversa, um novo contato é criado com nome/email vindos do Typebot. Assim, dados coletados no fluxo (ex.: formulário) ficam alinhados ao cadastro de contatos.

---

## 4. Cenários desejados

| Cenário | Hoje | Com Typebot (proposta) |
|--------|------|-------------------------|
| **Fluxo ao entrar no departamento** | Só se a conversa **nasce** ou **reabre** nesse departamento. Transferência manual **não** dispara fluxo. | Manter regra do Sense; **adicionar**: ao **transferir** conversa para um departamento, chamar `try_send_flow_start(conversation)`. Se o fluxo do departamento for Typebot, iniciar sessão Typebot e passar `conversation_id`, `contact_phone`, `tenant_id`. |
| **Ativar fluxo dentro da conversa** | Não existe. | Botão “Iniciar fluxo” no chat (ou ação do agente) que chama um endpoint que dispara o fluxo configurado para aquele departamento/Inbox (Sense ou Typebot). |
| **Edição visual do fluxo** | Canvas próprio (FlowCanvas) no Sense. | **Opção A**: manter canvas. **Opção B**: substituir por iframe do Typebot (cada Flow guarda `typebot_public_id` + URL base do Typebot). **Opção C**: híbrido – fluxos “simples” no Sense; fluxos “Typebot” só exibem iframe e config (public ID, variáveis). |

---

## 5. Proposta técnica resumida

### 5.1 Separação por tenant
- Cada **Flow** continua atrelado ao **tenant** (já é assim).
- Novo campo opcional no **Flow**: `typebot_public_id` (e, se necessário, `typebot_base_url` para self-hosted). Se preenchido, o “motor” do fluxo é o Typebot; senão, continua o motor atual (FlowNode + FlowEdge + flow_engine).

### 5.2 Iframe no lugar do canvas (quando for Typebot)
- Na **FlowPage**, se `flow.typebot_public_id` estiver preenchido:
  - Em vez de renderizar o **FlowCanvas**, renderizar um **iframe** do Typebot (URL do embed + query params ou postMessage com `tenantId`, `flowId`, etc.).
- URL do iframe pode ser construída com base em configuração do tenant (ex.: `TenantAiSettings` ou novo campo em Tenant/Config) para URL base do Typebot (cloud ou self-hosted).

### 5.3 Disparar fluxo ao “entrar” no departamento
- No endpoint de **transferência** de conversa (`ConversationViewSet.transfer`), após atualizar `conversation.department` (e `assigned_to` se for o caso), chamar `try_send_flow_start(conversation)`.
- Assim, ao transferir para um departamento que tem fluxo (Sense ou Typebot), o fluxo inicia na hora.

### 5.4 Ativar fluxo dentro da conversa
- Novo endpoint, ex.: `POST /chat/conversations/{id}/start-flow/` (ou “aplicar fluxo do departamento atual / do Inbox”).
- Backend: `try_send_flow_start(conversation)` (e, no futuro, se for Typebot, iniciar sessão e enfileirar envio das primeiras mensagens ao WhatsApp).
- Frontend: botão “Iniciar fluxo” (ou “Enviar menu”) na barra da conversa ou no menu de ações.

### 5.5 Execução Typebot ↔ WhatsApp
- **Sense → Typebot**: ao iniciar fluxo Typebot, `POST startChat` com `prefilledVariables`: `tenant_id`, `conversation_id`, `contact_phone`, `department_id` (opcional).
- **Typebot → Sense**: usar **webhooks** do Typebot (quando o bot “envia” uma mensagem) para um endpoint Sense que envia a mensagem via Evolution/Meta (igual ao envio atual de mensagens do fluxo).
- **Sense → Typebot**: no webhook de mensagem recebida, se a conversa estiver em “fluxo Typebot” (ex.: guardar `ConversationFlowState` com `metadata: { engine: 'typebot', session_id: '...' }`), chamar `continueChat` com o texto e depois processar a resposta (webhook) e enviar ao WhatsApp.

---

## 6. Próximos passos sugeridos

1. **Imediato (sem Typebot)** — ✅ **Feito**  
   - Chamar `try_send_flow_start(conversation)` após **transferência** de conversa para um departamento.  
   - Adicionar ação “Iniciar fluxo” no chat (endpoint + botão na UI).

2. **Typebot – fase 1 (config + iframe)** — ✅ **Feito**  
   - Campos no modelo: `Flow.typebot_public_id`, `Flow.typebot_base_url` (opcional).  
   - Na FlowPage, se `typebot_public_id` existir, mostrar iframe do Typebot em vez do canvas; senão, manter canvas atual.

3. **Typebot – fase 2 (execução)** — ✅ **Feito** (implementado via resposta da API startChat/continueChat, sem webhook do Typebot)  
   - Ao iniciar fluxo “Typebot”: criar sessão via API, persistir `session_id` no estado da conversa, as mensagens do bot vêm do body da resposta da API e são enviadas ao WhatsApp pelo Sense.  
   - No webhook de mensagem recebida, se sessão Typebot ativa, chamar `continueChat` e enviar as mensagens de resposta ao WhatsApp.

4. **Multi-tenant** — ✅ **Feito** — ✅ **Feito**  
   - Cada tenant pode ter sua própria URL base do Typebot (self-hosted por cliente) ou usar um Typebot cloud com `publicId` por fluxo/departamento; o Sense só guarda `typebot_public_id` (e opcionalmente base URL) por Flow, já isolado por tenant.

**Opcional / futuro:** token de API do Typebot (se exigido); suporte a imagem/áudio nas respostas do Typebot; limpeza de sessão ao fim do fluxo.

---

## 7. Referências

- Typebot – Iframe: https://docs.typebot.io/deploy/web/iframe  
- Typebot – API (startChat / continueChat): https://docs.typebot.io/deploy/api/overview  
- Typebot – Variáveis: https://docs.typebot.io/editor/variables  
- Sense – Motor de fluxo: `backend/apps/chat/services/flow_engine.py`  
- Sense – Disparo do fluxo: `try_send_flow_start` em `backend/apps/chat/webhooks.py` (nova conversa e conversa reaberta).
