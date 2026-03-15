# Revisão detalhada: Sidebar de conversas V2

Documento de revisão da implementação da nova sidebar de conversas (ChatConversationSidebarWrapper + ConversationSidebar), ativada por `VITE_CHAT_UI_V2=true`.

---

## 1. Arquitetura e escopo

| Aspecto | Situação |
|--------|----------|
| **Escopo da V2** | Apenas a **lista de conversas** (sidebar) foi trocada. ChatWindow, MessageList, MessageInput e fluxos de mensagens permanecem inalterados. |
| **Flag de feature** | `import.meta.env.VITE_CHAT_UI_V2 === 'true'` em `ChatPage.tsx`; fallback para `ConversationList` quando não definido ou diferente. |
| **Compatibilidade** | Store (Zustand), WebSocket, conversationUpdater e APIs são compartilhados; não há duplicação de estado entre V1 e V2. |

---

## 2. Arquivos criados/alterados

### Novos arquivos
- `frontend/src/utils/sentiment.ts` – tipos e config de sentimento (positive/negative/neutral).
- `frontend/src/utils/formatTime.ts` – `formatTimeAgo`, `formatTimeRelative` (date-fns + pt-BR).
- `frontend/src/components/chat/adapters.ts` – tipos da spec (ConversationSidebarConversation, ChatPanelContact, ChatPanelMessage) e funções `conversationToSidebarItem`, `messageToPanelMessage`.
- `frontend/src/components/chat/DateSeparator.tsx` – separador de data (ex.: "Hoje", "Ontem").
- `frontend/src/components/chat/TypingIndicator.tsx` – indicador de digitação (bolinhas animadas).
- `frontend/src/components/chat/MessageBubble.tsx` – balão de mensagem (spec do painel); usado quando/onde o painel V2 for adotado.
- `frontend/src/components/chat/ConversationSidebar.tsx` – componente **apresentacional**: lista virtualizada, busca opcional, botão nova conversa, avatar, preview, tempo, unread, sentimento.
- `frontend/src/modules/chat/hooks/useConversationListData.ts` – hook de dados: fetch inicial, abas Minhas conversas/Grupos, refresh 30s, loading/erro/retry.
- `frontend/src/modules/chat/components/ChatConversationSidebarWrapper.tsx` – wrapper: usa o hook + store, filtro/ordenação, deep link, empty states, NewConversationModal.

### Arquivo alterado
- `frontend/src/modules/chat/components/ChatPage.tsx` – condicional que renderiza `ChatConversationSidebarWrapper` ou `ConversationList` conforme a flag.
- `frontend/index.css` – variáveis CSS de chat (--chat-bg, --chat-bubble-in/out, etc.) em `:root` e `.dark`.
- `frontend/package.json` – dependência `@tanstack/react-virtual`.
- `frontend/.env` – `VITE_CHAT_UI_V2=true` (opcional).

---

## 3. Comportamento vs ConversationList (paridade)

| Funcionalidade | ConversationList | Sidebar V2 | Observação |
|----------------|------------------|------------|------------|
| Fetch inicial (uma vez) | Sim | Sim (hook) | Hook chama clearUpdateCache + upsert; mesmo critério. |
| Aba Minhas conversas | Fetch com `assigned_to_me` | Idem | Mesmos params e merge. |
| Aba Grupos | Fetch com `conversation_type=group`, `page_size=100` | Idem | Idem. |
| Refresh periódico 30s | Sim | Sim (hook) | Silencioso em background. |
| Busca (debounce 300ms) | Por nome, telefone, group_name | Idem | Mesmo filtro no wrapper. |
| Filtro por departamento | Inbox, my_conversations, groups, departamento específico | Idem | Mesma lógica no useMemo do wrapper. |
| Ordenação Grupos | Por last_message_at; sem data → alfabética | Idem | Idem. |
| Modo “Aguardando resposta” | Filtra última msg incoming; ordena mais atrasada primeiro; fixa ativa no topo | Idem | Idem. |
| Preview em grupos | "sender_name: preview" | Idem | Adapter ajustado para incluir sender_name. |
| Preview sem texto (só anexo) | "📎 Anexo" | Idem | messageToPanelMessage e adapter. |
| Deep link `?conversation_id=` | Seleciona conversa e limpa URL | Idem | useEffect no wrapper. |
| Empty: loading | 3 bolinhas + “Carregando conversas...” | Idem | Idem. |
| Empty: erro inicial | Mensagem + “Tentar novamente” (reseta hasLoaded) | Idem | Idem. |
| Empty: erro de aba (my_conversations/groups) | Mensagem + “Tentar novamente” (retryTrigger) | Idem | Idem. |
| Empty: nenhuma conversa | “Nenhuma conversa” / “Nenhum grupo” + Sync grupos / “Nenhuma aguardando” + Desative o filtro | Idem | Idem. |
| NewConversationModal | Sim | Sim | Aberto pelo botão “Nova conversa”. |
| Sincronizar grupos (empty) | POST sync-groups, toast, retry | Idem | Idem. |
| Busca/novo ocultos na aba Grupos | Sim | Sim | showSearchAndNew = activeDepartment?.id !== 'groups'. |

---

## 4. Diferenças conhecidas (V2 em relação à V1)

| Item | V1 (ConversationList) | V2 (Sidebar) |
|------|------------------------|--------------|
| **Modo espião** | Botão “olho” por item (admin/gerente); abre sem marcar como lida | Não implementado na V2. Quem precisar pode reativar na sidebar (mesmo store: setOpenInSpyMode). |
| **Tags/instância no item** | Exibe tags do contato e instância no item da lista | Não exibidas na V2 (layout simplificado). |
| **“Fulano está atendendo”** | Badge no item quando assigned_to e não é “Minhas conversas” | Não exibido na V2. |
| **Foto do contato/grupo** | profile_pic_url com fallback para iniciais | Só iniciais + cor por hash (sem foto). |
| **Lista** | Scroll tradicional (todos os itens no DOM) | Lista virtualizada (@tanstack/react-virtual), altura fixa 72px. |

Nenhuma dessas diferenças altera MessageList, MessageInput ou ChatWindow; apenas a apresentação da lista de conversas.

---

## 5. Adapters e tipos

- **conversationToSidebarItem**: usa getDisplayName (phoneFormatter), getMessagePreviewText (messageUtils), last_message_at/updated_at/created_at, unread_count, sentiment do último attachment ou da mensagem. Grupos: iniciais do group_name ou "👥"; preview com "sender_name: preview" quando houver sender_name.
- **messageToPanelMessage**: direction incoming→inbound, outgoing→outbound; status seen→read, delivered→delivered, sent→sent; conteúdo vazio com anexos → "📎 Anexo"; senderInitials a partir de sender_data ou sender_name.
- **ChatPanelMessage.status** hoje é só `'sent' | 'delivered' | 'read'`. Mensagens `pending` ou `failed` são mapeadas para um desses (MessageBubble não trata ícone de falha); extensão futura possível.

---

## 6. Acessibilidade e UX

- Busca: `aria-label="Buscar conversas ou contatos"`.
- Botão nova conversa: `aria-label="Nova conversa"`, `title="Nova conversa"`.
- Lista: `aria-label="Lista de conversas"`.
- Itens: `role="button"`, `tabIndex={0}`, teclas Enter e Espaço disparam onSelect.
- Bolinha de sentimento: `title={sentiment.label}`; avatar com `aria-hidden` onde for decorativo.
- Loading e botões de retry/empty com textos claros em português.

---

## 7. Performance

- Lista virtualizada: apenas itens visíveis + overscan (8) no DOM; reduz uso de memória e re-renders com muitas conversas.
- useMemo para filteredConversations e sidebarItems no wrapper; dependências corretas.
- Hook useConversationListData: fetches condicionais por aba; refresh em intervalo fixo, sem acumular timers.
- Store: seletores com shallow no wrapper para evitar re-renders desnecessários.

---

## 8. Edge cases e robustez

| Caso | Tratamento |
|------|------------|
| conversation_id no deep link mas conversa ainda não carregada | Comportamento igual à V1: só seleciona se a conversa existir em `conversations`; não há fetch por ID. |
| Lista vazia após fetch | Empty state “Nenhuma conversa” / “Nenhum grupo” etc., com ações corretas (nova conversa, sync grupos, desativar filtro). |
| Troca rápida de abas | Vários fetches podem disparar; cada um faz clearUpdateCache + upsert; estado final consistente. |
| activeId string vs number | Comparação com String(item.id) === String(activeId) na sidebar. |
| last_message_at inválido | formatTimeAgo/formatTimeRelative (formatTime.ts) retornam '' para datas inválidas. |
| Grupos sem group_name | getDisplayName(conv) e iniciais do nome; adapter usa group_metadata?.group_name \|\| name. |

---

## 9. Segurança e manutenção

- Sem novas chamadas de API além das já usadas pela ConversationList; mesma base (api, ApiErrorHandler).
- Conteúdo de mensagem no preview passa por getMessagePreviewText (sem renderização HTML crua na sidebar).
- Nenhuma migration ou alteração de backend exigida pela sidebar V2.

---

## 10. Checklist pós-revisão

- [x] Paridade de filtro/ordenação com ConversationList.
- [x] Preview em grupos com "sender_name: preview" (e "📎 Anexo" quando aplicável).
- [x] Deep link ?conversation_id.
- [x] Empty states e retry (inicial e por aba).
- [x] Sync grupos no empty da aba Grupos.
- [x] NewConversationModal e botão Nova conversa.
- [x] Busca com debounce; oculta na aba Grupos.
- [x] Acessibilidade básica (aria, teclado).
- [x] Lista virtualizada e performance.
- [ ] Modo espião na V2 (opcional; deixado para frente).
- [ ] Foto do contato na V2 (opcional).
- [ ] Tags/instância no item da lista (opcional).

---

## 11. Como ativar e reverter

- **Ativar V2:** no `frontend/.env`, definir `VITE_CHAT_UI_V2=true` e reiniciar o dev server (ou rebuild).
- **Reverter:** remover a variável ou definir `VITE_CHAT_UI_V2=false` e reiniciar/rebuild. A ConversationList continua disponível e inalterada.

Esta revisão reflete o estado da implementação após a correção do preview em grupos no adapter e a checagem de paridade com o ConversationList.
