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
