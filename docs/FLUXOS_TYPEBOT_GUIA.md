# Guia: Fluxos Typebot no Sense

Guia de uso e configuração para quem vai configurar fluxos Typebot no Sense.

---

## Requisitos

- Script SQL dos campos Typebot aplicado: `backend/apps/chat/migrations/flow_typebot_fields.sql` (após `flow_schema.sql` ou migration 0017).
- Typebot publicado (no Typebot: **Share > API**) com Public ID obtido.
- API do Typebot acessível (typebot.io ou self-hosted).

---

## Quando o fluxo dispara

O fluxo (Sense ou Typebot) é iniciado nos seguintes casos:

- **Nova conversa** (primeira mensagem no Inbox ou em um departamento com fluxo).
- **Conversa reaberta** (conversa estava fechada e chega nova mensagem).
- **Transferência** para um departamento que tem fluxo ativo (o endpoint de transferência chama o início do fluxo).
- **Botão "Iniciar fluxo"** no menu da conversa (três pontos), que chama o endpoint `start-flow` e reinicia o fluxo do escopo atual (Inbox ou departamento).

---

## Como configurar um fluxo Typebot

1. Acesse **Configurações > Fluxos**.
2. Crie um novo fluxo (informe só o nome) e salve.
3. **Edite** o fluxo (os campos Typebot só aparecem na edição, não na criação).
4. No modal **"Editar fluxo"**, preencha:
   - **Typebot Public ID**: no Typebot, aba **Share > API** — o Public ID aparece na URL ou no painel.
   - **URL base da API** (opcional): deixe vazio para usar typebot.io; para self-hosted, informe a URL base da API (ex.: `https://meutypebot.com/api/v1`).
5. Salve. A partir daí, o fluxo passa a ser executado pelo Typebot (startChat/continueChat); as mensagens do bot são enviadas ao WhatsApp pelo Sense.

---

## Variáveis enviadas ao Typebot

No **startChat**, o Sense envia as seguintes variáveis em `prefilledVariables`:

| Variável         | Descrição                                      |
|------------------|------------------------------------------------|
| `conversation_id`| ID da conversa no Sense                        |
| `contact_phone`  | Telefone do contato                            |
| `contact_name`   | Nome do contato (ou "Contato" se vazio)        |
| `tenant_id`      | ID do tenant                                   |
| `department_id`  | ID do departamento (se a conversa tiver depto) |

Você pode usar essas variáveis nos blocos do Typebot (texto, condições, etc.).

### Variáveis extras por fluxo

No **Editar fluxo** (ou via API no campo `typebot_prefilled_extra`) você pode definir um JSON com variáveis adicionais que serão enviadas em todo **startChat** desse fluxo. Exemplo: `{"campanha": "black-friday", "origem": "whatsapp"}`. No Typebot, crie variáveis com os mesmos nomes para usá-las. Chaves e valores são enviados como string.

### Consultar variáveis do Typebot e mapear no cadastro

Se você informar no fluxo o **ID interno do Typebot** (o ID que aparece na URL ao editar o typebot no dashboard) e a **API key** do dashboard (Settings > API no Typebot), o Sense pode **buscar a lista de variáveis** que o fluxo usa e mostrar no modal de edição. Assim você:

1. Clica em **"Carregar variáveis do Typebot"** e o Sense chama a API do dashboard do Typebot (Builder API).
2. A lista de variáveis do fluxo aparece; você preenche o valor desejado para cada uma (ou deixa vazio).
3. Clica em **"Aplicar ao JSON de variáveis extras"** e o Sense monta o `typebot_prefilled_extra` com esse mapeamento.

Isso exige que o Typebot esteja publicado e que você use a **API do dashboard** (não a API pública de chat): a API pública (startChat) não retorna a lista de variáveis; só a API do Builder (com token) retorna o typebot publicado com o array `variables`. Para self-hosted, a URL base do fluxo é usada também como base do Builder (mesmo servidor).

---

## Receber informações do Typebot no Sense

### resultId

O Sense guarda o **resultId** retornado pelo Typebot no **startChat** em `ConversationFlowState.metadata["typebot_result_id"]`. Assim você pode usar a API do Typebot (GET result) com esse ID para buscar variáveis/resultado depois, se precisar.

### Webhook: Typebot envia variáveis para o Sense

O Sense expõe um webhook para o Typebot enviar variáveis de volta em tempo real:

- **URL:** `POST /api/chat/webhooks/typebot/` (base do backend do Sense).
- **Autenticação:** nenhuma (o endpoint é público; use em ambiente controlado).
- **Body (JSON):**
  - `session_id` (opcional): o `sessionId` retornado pelo startChat. No Typebot você pode passar isso em uma variável (o Sense envia `conversation_id` em prefilledVariables; para session_id o Typebot não o tem por padrão — use `result_id` se não tiver session_id).
  - `result_id` (opcional): o `resultId` retornado pelo startChat. No Typebot pode ser obtido com o bloco **Set variable** usando o valor "Result ID".
  - `variables` (obrigatório): objeto com as variáveis a salvar. Ex.: `{"nome": "João", "email": "j@x.com", "opcao_escolhida": "vendas"}`.

**Exemplo no Typebot:** use um bloco **Webhook** com:

- URL: `https://seu-backend-sense.com/api/chat/webhooks/typebot/`
- Body (JSON): `{ "result_id": "{{resultId}}", "variables": { "nome": "{{nome}}", "email": "{{email}}" } }`

(No Typebot, use as variáveis do fluxo no lugar de `{{resultId}}`, `{{nome}}`, etc.)

O Sense persiste em:

- `ConversationFlowState.metadata["typebot_variables"]` (acumula chamadas)
- `Conversation.metadata["typebot_result"]` com `variables` e `updated_at`

Assim você pode consultar na conversa (API ou no chat) os dados que o Typebot coletou.

### Consultar variáveis recebidas

- **Conversação:** o objeto `Conversation` pode ter `metadata["typebot_result"]` com `variables` e `updated_at` após o webhook ter sido chamado.
- **Estado do fluxo:** `ConversationFlowState.metadata["typebot_variables"]` contém as variáveis enviadas pelo Typebot (e `metadata["typebot_result_id"]` o resultId do startChat).

---

## Como testar

- **Na FlowPage:** selecione o fluxo Typebot e use a seção **"Enviar passo inicial (teste)"**: informe um número que já tenha conversa no Sense e clique em **"Enviar teste"**. O Sense inicia a sessão Typebot e envia as primeiras mensagens para esse número.
- **No chat:** abra uma conversa, clique no menu (três pontos) e em **"Iniciar fluxo"**. O fluxo do Inbox ou do departamento da conversa será iniciado.

Se o teste falhar, confira o **Public ID** (Share > API no Typebot) e a **URL base** (deixe vazia para typebot.io).

---

## Fluxo inicia mas nenhuma mensagem chega ao WhatsApp

- **Primeiro bloco do Typebot:** o Sense só envia ao WhatsApp mensagens do tipo **texto** retornadas pela API. Se o primeiro bloco do fluxo for só um input (pergunta sem texto de boas-vindas) ou outro tipo (imagem, etc.), a API pode retornar 0 mensagens e o cliente não recebe nada. Inclua um bloco de **texto** no início (ex.: "Olá! Em que posso ajudar?") antes do primeiro input.
- **Logs:** no servidor, procure por `[TYPEBOT]`. Se aparecer "startChat retornou 0 mensagens de texto" e "types=...", o Typebot respondeu mas sem mensagens de texto; ajuste o fluxo no Typebot.
- **Resposta da API start-flow:** se o frontend mostrar o aviso "Fluxo iniciado, mas o Typebot não enviou nenhuma mensagem", o backend retornou `messages_queued: 0`; confira o primeiro bloco do fluxo no Typebot.

---

## Typebot cloud vs self-hosted

- **Typebot cloud (typebot.io):** deixe a URL base vazia. O Sense usa `https://typebot.io/api/v1` para startChat/continueChat.
- **Self-hosted:** preencha a URL base da API (ex.: `https://meutypebot.com` ou `https://meutypebot.com/api/v1`; o código normaliza se faltar `/api/v1`).
- O **iframe** na FlowPage (visualização do fluxo) usa a URL de visualização: base sem `/api/v1` + `/embed/{publicId}`. Ex.: `https://typebot.io/embed/xxx` ou `https://meutypebot.com/embed/xxx`.

---

## Observação sobre o envio das mensagens

As mensagens do bot ao WhatsApp são as retornadas no **body da resposta** da API (startChat e continueChat). O Sense **não** usa webhook do Typebot para enviar ao WhatsApp: a cada resposta do usuário, o webhook do Sense chama continueChat e envia as mensagens que a API retorna.

---

## Referências de código

Para detalhes técnicos da implementação:

- **Backend:** `backend/apps/chat/models_flow.py`, `backend/apps/chat/services/typebot_flow_service.py`, `backend/apps/chat/services/flow_engine.py`, `backend/apps/chat/webhooks.py`, `backend/apps/chat/api/views.py`, `backend/apps/chat/api/views_flow.py`, `backend/apps/chat/api/serializers_flow.py`
- **Frontend:** `frontend/src/pages/FlowPage.tsx`, `frontend/src/modules/chat/components/ChatWindow.tsx`
- **Documentação técnica:** [FLUXOS_TYPEBOT_INTEGRACAO.md](FLUXOS_TYPEBOT_INTEGRACAO.md)

Documentação Typebot:

- [Iframe](https://docs.typebot.io/deploy/web/iframe)
- [API (startChat / continueChat)](https://docs.typebot.io/deploy/api/overview)
- [Variáveis](https://docs.typebot.io/editor/variables)
