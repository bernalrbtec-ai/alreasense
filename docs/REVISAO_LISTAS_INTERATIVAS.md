# Revisão final: listas interativas Meta

## Escopo implementado

- **Fase 1 – Recebimento e renderização:** Webhook Evolution (`listMessage`, `listResponseMessage`), webhook Meta (logging + `description` em `list_reply`), frontend (render de `interactive_list`, helper de placeholders, placeholders em todos os pontos).
- **Fase 2 – Envio:** Provider `send_interactive_list`, consumer com validações e bloqueios, task Meta 24h, frontend (transporte + modal de lista).
- **Documentação:** [LISTAS_INTERATIVAS_META.md](LISTAS_INTERATIVAS_META.md) para suporte.
- **Testes:** [backend/apps/chat/tests/test_interactive_list.py](../backend/apps/chat/tests/test_interactive_list.py) – 21 testes: provider (validações e payload válido), parsing Evolution (listMessage/listResponse e fallback), consumer (rejeição flag desligada, não-Meta, lista+template). Parsing extraído em [apps/chat/utils/evolution_list_parsing.py](../backend/apps/chat/utils/evolution_list_parsing.py).

---

## Backend

### Webhook Evolution (`apps/chat/webhooks.py`) e parsing (`apps/chat/utils/evolution_list_parsing.py`)

- Variáveis `interactive_list_metadata` e `list_reply_metadata` inicializadas; preenchidas em `listMessage` e `listResponseMessage`.
- Lógica de listMessage/listResponse e fallback de lista extraída em [evolution_list_parsing.py](../backend/apps/chat/utils/evolution_list_parsing.py) (`parse_list_message`, `parse_list_response`, `parse_list_message_fallback`); webhook chama essas funções.
- `listMessage`: extração de body, buttonText, header/footer, sections/rows (suporte a `values`, `rowIds`, `rowId`, `displayText`); **limite de 10 rows no total**; **fallback para `rowIds` como lista de strings** (id/title = valor); fallback quando o payload vem com outro `messageType` (mesmo limite e fallback rowIds); logging com instance e quantidade de seções.
- `listResponseMessage`: extração de título e id da opção; `content` e `list_reply` em metadata; logging.
- `message_defaults['metadata']`: atribuição de `interactive_list` (com safe_il) e `list_reply`; tratamento de serialização.
- **Merge (from_me):** preservação de `interactive_list` quando a mensagem já tem sections/rows ricas e o webhook traz dados piores (mesmo padrão de `interactive_reply_buttons`); mesma lógica na mensagem vinculada (candidato sem message_id).

### Webhook Meta (`apps/connections/meta_webhook.py`)

- `list_reply`: `content = title`, `metadata['list_reply']` com id e title; opcionalmente `description` até 72 caracteres.
- Log em nível info ao processar `list_reply` (conversation_id e título).

### Provider Meta (`apps/notifications/whatsapp_providers/meta_cloud.py`)

- `send_interactive_list(phone, body_text, button_text, sections, header_text=None, footer_text=None, quoted_message_id=None)`.
- Rejeição (sem truncar): body vazio ou > 1024; button vazio ou > 20; header/footer > 60; section title > 24; **row com título vazio** (erro `INVALID_ROW_TITLE`: "Cada opção deve ter um título"); row title > 24; row description > 72; sem seções; seção sem rows; total de rows > 10; ids duplicados.
- Payload: `type: interactive`, `interactive.type: list`, body, action.button, action.sections; header/footer opcionais; `context.message_id` quando há reply.
- Logging em sucesso e em falha.

### Consumer (`apps/chat/consumers_v2.py`)

- Leitura de `interactive_list`; rejeição se vier com template, botões ou anexos.
- Validação: body_text, button_text, sections não vazias; **cada row com título não vazio** (rejeição com `INVALID_INTERACTIVE_LIST`); 1–10 rows no total; ids únicos; limites (body 1024, button 20, header/footer 60).
- Feature flag `allow_meta_interactive_buttons`; conversa individual; `get_conversation_is_meta_provider` para bloquear em não-Meta.
- `create_message(..., interactive_list=None)`: normalização e gravação em `metadata['interactive_list']` com **máximo 10 rows no total**; só grava `interactive_list` quando há ao menos uma seção com rows (evita estado inconsistente); rows com título vazio omitidas na gravação.

### Task (`apps/chat/tasks.py`)

- Branch Meta 24h: se existir `metadata.interactive_list` válido (body_text, button_text, sections), verifica janela 24h; fora da 24h marca mensagem como falha e faz broadcast; dentro chama `send_interactive_list` com `quoted_message_id` (já definido antes no fluxo).
- **Retry automático:** até 3 tentativas; em falha **transitória** (RATE_LIMIT, EXCEPTION ou status HTTP >= 500) aguarda 3s e tenta de novo; `status_code` tratado com conversão segura para int.
- Em sucesso: atualiza message_id (Meta wamid), status sent, broadcast; em falha (após retries): status failed, error_message, broadcast.

---

## Frontend

### Utils (`messageUtils.ts`)

- `getMessagePreviewText(content, metadata)`: centraliza placeholders (`[listMessage]`, `[buttonsMessage]`, etc.); retorna "Mensagem com lista" quando `metadata.interactive_list` existe.

### MessageList

- Uso de `getMessagePreviewText` para conteúdo e reply preview.
- Bloco de leitura para `metadata.interactive_list`: header, body, button_text, seções/rows (sem clique).

### ConversationList, MessageInfoModal, ForwardMessageModal, MessageInput

- Uso de `getMessagePreviewText` para preview/placeholder (incluindo lista).

### ChatWebSocketManager

- `sendChatMessageWithList(conversationId, bodyText, buttonText, sections, headerText?, footerText?, replyTo?)`: monta payload com `interactive_list`; **total de rows limitado a 10** (Meta), preservando ordem e seções; limites (button 20, header/footer 60, section title 24, row title 24, description 72); envia `reply_to` quando informado.

### useChatSocket / ChatWindow

- `sendMessageWithList` exposto e repassado ao MessageInput.

### MessageInput

- Botão lista (ícone ListOrdered) para conversa individual + Meta + flag; modal com body, button, header/footer opcionais, seções com rows (id, title, description); total de rows limitado a 10 na UI; envio com `reply_to` quando há mensagem respondida; reset do estado e `clearReply` após envio.

---

## Verificações feitas na revisão

- **Ordem de prioridade no Meta (task):** lista é tratada antes de botões e texto; botões e template continuam iguais.
- **Reply (quoted):** `quoted_message_id` vem do `metadata.reply_to` no início da task; é repassado para `send_interactive_list`; frontend envia `reply_to` no payload de lista.
- **Limites:** Backend (consumer + provider) rejeita ao exceder; frontend e manager aplicam slice para não enviar além do permitido.
- **Merge Evolution:** Preservação de `interactive_list` em from_me e na mensagem vinculada está alinhada ao padrão de `interactive_reply_buttons`.
- **Flag:** Uma única flag `allow_meta_interactive_buttons` para botões e lista; desligar desativa ambos.

---

## Edge cases e melhorias aplicadas

- **Row com título vazio:** Provider rejeita com `INVALID_ROW_TITLE` ("Cada opção deve ter um título"); consumer rejeita com `INVALID_INTERACTIVE_LIST` ("Cada opção deve ter um título (não vazio)"). Evita payload inválido na Meta.
- **Total de rows > 10 no recebimento:** Webhook Evolution (listMessage e fallback) limita o total de rows a 10 ao montar `sections`, alinhando ao limite da API Meta e evitando metadata desnecessariamente grande.
- **Total de rows > 10 no envio:** Frontend (`ChatWebSocketManager.sendChatMessageWithList`) passa a capar em 10 rows no total ao montar o payload, preservando a estrutura de seções; backend continua como autoridade e rejeita se exceder.
- **Consumer – cap 10 rows ao salvar:** Em `create_message`, o metadata `interactive_list` é montado com no máximo 10 rows no total; só é gravado quando há ao menos uma seção com rows (evita body/button sem seções).
- **Evolution `rowIds` como strings:** Em listMessage e no fallback, quando o item da lista não é dict (ex.: `rowIds: ["id1","id2"]`), é criada row com id e title iguais ao valor (limitado 100/24 chars).
- **Task – retry em falha transitória:** Até 3 tentativas para `send_interactive_list`; retry apenas para RATE_LIMIT, EXCEPTION ou HTTP >= 500; delay 3s entre tentativas; `status_code` convertido para int de forma segura.
- **Settings – testes no Windows:** Prints em `alrea_sense/settings.py` sem emojis (prefixos ASCII), evitando `UnicodeEncodeError` ao rodar `manage.py test` no Windows.

---

## Possíveis melhorias futuras (não obrigatórias)

- **(Já feito)** Testes de consumer (rejeição lista+template, não-Meta, flag desligada) e de parsing Evolution (listMessage/listResponseMessage → metadata esperada) em test_interactive_list.py (21 testes no total).

---

## Maturidade para produção

### O que está pronto

| Área | Status | Detalhe |
|------|--------|---------|
| **Validação** | OK | Consumer + provider rejeitam payload inválido (body/button vazios, título vazio, >10 rows, ids duplicados, limites de caracteres). Frontend capa em 10 rows e exige ao menos uma opção. |
| **Erro ao usuário** | OK | Backend envia `type: 'error'` com `message`; frontend (`useChatSocket` → `handleError`) exibe `data.message` em `toast.error`. Mensagens de lista falhadas mostram `error_message` no MessageList/MessageInfoModal. |
| **Janela 24h** | OK | Task verifica `is_within_24h_window`; fora da janela marca mensagem como falha com texto claro e faz broadcast. |
| **Feature flag** | OK | `allow_meta_interactive_buttons` por tenant; desligar desativa lista (e botões) no consumer e na UI. |
| **Recebimento** | OK | Evolution (listMessage/listResponseMessage) e Meta (list_reply); merge from_me preserva `interactive_list`; limite de 10 rows ao montar sections. |
| **Segurança** | OK | Lista só em conversa individual e instância Meta; sem combinação com template/botões/anexos. Conteúdo da lista renderizado em React (escape por padrão). |
| **Observabilidade** | OK | Logs em webhook (listMessage/listResponseMessage/list_reply), provider (sucesso/falha), consumer (motivo da rejeição), task (24h e resultado do envio). |
| **Documentação** | OK | LISTAS_INTERATIVAS_META.md (suporte), REVISAO_LISTAS_INTERATIVAS.md (revisão e edge cases). |
| **Testes** | OK | 21 testes: provider (10), parsing Evolution listMessage/listResponse (6), consumer rejeições (3). Parsing em evolution_list_parsing.py; webhook usa esse módulo. |

### O que não é obrigatório antes de produção

- **(Já feito)** Testes de consumer e de parsing Evolution (webhook usa evolution_list_parsing); 21 testes no total.
- **(Já feito)** Normalização em `create_message`: total de rows capado a 10 ao salvar; só grava `interactive_list` quando há seções com rows.
- **(Já feito)** Evolution `rowIds` como lista de strings: fallback implementado em listMessage e fallback.
- **(Já feito)** Retry automático: task faz até 3 tentativas em falha transitória; mensagem failed continua com botão “Reenviar” na UI; task faz até 3 tentativas em falha transitória (RATE_LIMIT, EXCEPTION, 5xx) com delay 3s.

### Checklist pré-produção recomendado

1. **Staging:** Enviar lista em conversa Meta dentro da 24h → mensagem enviada e exibida no WhatsApp.
2. **Staging:** Enviar lista fora da 24h → mensagem falha com texto “Lista interativa só pode ser enviada dentro da janela de 24h”.
3. **Staging:** Enviar lista com 11 opções (se a UI permitir) ou via API → backend rejeita com mensagem clara; frontend mostra toast de erro.
4. **Staging:** Receber lista (Evolution ou Meta) → mensagem aparece com body, botão e opções no chat.
5. **Staging:** Desligar `allow_meta_interactive_buttons` no tenant → botão de lista some; envio de lista via API rejeitado.
6. **Produção:** Ligar a flag apenas para tenants que usarão listas; comunicar suporte (LISTAS_INTERATIVAS_META.md).

### Veredito

**Pronto para produção** desde que o checklist de smoke acima seja executado em staging. Não há dependências obrigatórias pendentes (migrações, feature flags novas ou mudanças breaking). Melhorias de teste e normalização de metadata são opcionais e podem ser feitas em seguida.

---

## Revisão final (pós-melhorias 2–5 e edge cases)

### Fluxo verificado

1. **Recebimento:** Evolution (`listMessage` / fallback) e Meta (`list_reply`) preenchem metadata; Evolution limita 10 rows e trata `rowIds` como lista de strings quando o item não é dict.
2. **Envio (WS):** Consumer valida body, button, sections, 1–10 rows, título não vazio, ids únicos; grava em `create_message` com no máximo 10 rows e só persiste `interactive_list` se `sections_out` não for vazio.
3. **Envio (task):** Task lê `metadata.interactive_list`; dentro da 24h chama `send_interactive_list` até 3 vezes em falha transitória (RATE_LIMIT, EXCEPTION, 5xx) com 3s de delay; converte `status_code` para int de forma segura; em sucesso ou falha final atualiza status e broadcast.
4. **Provider:** Rejeita título vazio, >10 rows, ids duplicados e demais limites; retorna `(bool, dict)` com `error_code` e opcionalmente `status_code`.

### Edge cases cobertos

- Lista com 0 seções válidas no consumer: não grava `interactive_list`; mensagem fica com `content` apenas.
- `status_code` não inteiro na task: conversão com try/except para int; valor inválido vira 0 (sem retry).
- Evolution com `rowIds` como strings: listMessage e fallback criam row com id/title = valor (até 10 rows no total).
- Settings no Windows: prints sem emoji permitem rodar testes sem `UnicodeEncodeError`.

### Estado do código

- **Backend:** webhooks.py (Evolution listMessage + fallback via evolution_list_parsing), evolution_list_parsing.py (parse_list_message, parse_list_response, parse_list_message_fallback), consumers_v2.py (cap 10 rows + só gravar se sections_out), tasks.py (retry 3x + status_code seguro), meta_cloud.py (sem alteração), alrea_sense/settings.py (prints ASCII).
- **Documentação:** Este arquivo atualizado com melhorias 2–5 e edge cases; LISTAS_INTERATIVAS_META.md para suporte.
- **Testes:** test_interactive_list.py – 21 testes (provider, parsing Evolution em evolution_list_parsing.py, consumer rejeições). Webhook Evolution usa evolution_list_parsing; comportamento coberto pelos testes de parsing.

### Veredito final

Implementação está consistente, com validações em todas as camadas, retry para falhas transitórias, normalização de metadata e tratamento de edge cases. Pronto para produção após o checklist de smoke em staging descrito acima.

---

## Conclusão

A implementação está alinhada ao plano em duas fases (recebimento/renderização primeiro, envio depois), com validações, limites, logging, feature flag e preservação de metadata no merge. Foram aplicadas as melhorias 2–5 (cap 10 rows no consumer, fallback rowIds, retry na task, settings sem emoji) e revisões de edge cases (só gravar interactive_list com seções; status_code seguro). Nenhuma migração de banco foi necessária. Documentação e testes (provider, parsing Evolution, consumer) foram adicionados (21 testes). Pronto para uso em produção após o checklist de smoke do plano (Fase 1 e Fase 2 em staging, smoke de botões e templates).
