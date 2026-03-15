# Transferência e encerramento de conversas

Visão geral de como funcionam **transferência de departamento/agente** e **encerramento (fechar conversa)** no chat.

---

## 1. Transferência de conversa

### 1.1 Onde está na interface
- Menu da conversa (três pontos) → **Transferir conversa** (visível se o usuário tem permissão `can_transfer_conversations`).
- Abre o **TransferModal**: departamento atual, seleção de **novo departamento** e **novo agente**, motivo opcional.

### 1.2 Endpoint
- **POST** `/chat/conversations/{id}/transfer/`
- Body: `{ "new_department": "uuid?", "new_agent": "uuid?", "reason": "string?" }`
- Pelo menos um de `new_department` ou `new_agent` é obrigatório.

### 1.3 Regras no backend
- Conversa deve ser do mesmo **tenant** do usuário.
- Usuário deve ser admin, gerente ou agente.
- **Departamento**: deve existir e ser do tenant; agente/gerente só pode atribuir agente em departamentos aos quais pertence.
- **Agente**: deve pertencer ao departamento (novo ou atual da conversa).
- Se informar só **novo departamento**: conversa vai para a fila do departamento (`assigned_to = None`).
- Se informar **novo agente** (com ou sem departamento): conversa é atribuída ao agente; se também informar departamento, a conversa muda de departamento.

### 1.4 Efeitos colaterais
- **Fluxo (Typebot/Sense):** Se a transferência **atribui um agente** (`assigned_to` preenchido), o estado do fluxo é removido (`ConversationFlowState` apagado) — humano assumiu.
- **Mensagem interna:** Cria mensagem do tipo “Conversa transferida: De: … Para: …” (e motivo se houver), `is_internal=True`.
- **Fluxo do novo departamento:** Se o **departamento mudou**, o backend chama `try_send_flow_start(conversation)` — pode enviar menu/lista ou iniciar Typebot do departamento de destino.
- **Mensagem ao cliente:** Se o departamento mudou e o departamento de destino tem `transfer_message` configurado, essa mensagem é enviada ao WhatsApp do contato; senão, envia texto padrão (“Sua conversa foi transferida para o departamento X…”).
- **WebSocket:** `broadcast_conversation_updated`; se há agente atribuído, notificação `conversation_transferred` para esse agente.

### 1.5 Frontend após transferir
- Recarrega a lista de conversas.
- Se o usuário **não tiver mais acesso** à conversa (ex.: transferiu para outro departamento do qual não faz parte), a conversa é removida da lista e a ativa é limpa.
- Caso contrário, atualiza a conversa na lista e, se era a ativa, atualiza a conversa ativa com a resposta do backend.

---

## 2. Encerrar (fechar) conversa

### 2.1 Onde está na interface
- Menu da conversa (três pontos) → **Fechar conversa** (conversas individuais; não grupos).
- Cor vermelha para destacar a ação destrutiva.

### 2.2 Endpoint correto
- **POST** `/chat/conversations/{id}/close/`
- **Sem body** (ou body vazio).

**Importante:** Não usar **PATCH** com `{ "status": "closed" }`. O endpoint de fechar faz mais do que só mudar o status: marca mensagens não lidas como lidas, limpa departamento e atendente e remove o estado do fluxo. Usar PATCH deixaria a conversa “fechada” só no status, com departamento/atendente e fluxo ainda ativos.

### 2.3 O que o backend faz ao fechar
1. Marca todas as mensagens **incoming** com status `sent` ou `delivered` como **seen** (evita contagem de “não lidas” em conversas fechadas).
2. Define `status = 'closed'`, `department = None`, `assigned_to = None`.
3. Remove **ConversationFlowState** (para o fluxo Typebot/Sense).
4. Retorna a conversa serializada (para o frontend atualizar a lista).

### 2.4 Outros pontos que fecham conversa
- **Menu de boas-vindas:** opção “Encerrar” configurada no welcome menu chama `WelcomeMenuService._close_conversation(conversation)` (mesma lógica: status, department, assigned_to, fluxo).
- **Comando:** `close_inbox_idle_conversations` — fecha conversas no Inbox após X minutos sem interação (configurável); também apaga `ConversationFlowState`.
- **Timeout do welcome menu:** `check_welcome_menu_timeouts` pode chamar `_close_conversation` quando o cliente não escolhe opção no tempo configurado.

### 2.5 Frontend após fechar
- Chama **POST** `.../close/` e usa a **resposta** para atualizar a conversa no store (`updateConversation(data)`), em vez de montar um objeto local com só `status: 'closed'`.
- Atualiza contadores de departamentos (refetch de `/auth/departments/`).
- Fecha o menu e limpa a conversa ativa (`setActiveConversation(null)`).

---

## 3. Resumo rápido

| Ação | Endpoint | Efeito principal |
|------|----------|-------------------|
| Transferir | POST `.../transfer/` | Muda departamento e/ou agente; pode enviar fluxo e mensagem ao cliente; remove fluxo se humano assumir. |
| Fechar conversa | POST `.../close/` | status=closed, department/assigned_to=None, mensagens lidas, remove estado do fluxo. |

---

## 4. Configurações úteis

- **Departamento:** campo `transfer_message` (Configurações > Departamentos) — mensagem enviada ao cliente quando a conversa é **transferida para esse departamento**. Se vazio, usa o texto padrão.
- **Welcome menu:** `show_close_option` e `close_option_text` — opção no menu para o cliente encerrar a conversa; `_close_conversation` é chamada ao escolher.
- **Permissões:** `can_transfer_conversations` controla exibição do botão “Transferir conversa” no menu.
