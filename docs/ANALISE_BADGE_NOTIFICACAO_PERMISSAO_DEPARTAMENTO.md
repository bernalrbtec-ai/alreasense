# Análise: Badge e notificação para usuário sem permissão no departamento

## Problema

Usuário que só tem permissão em um departamento (ex.: Financeiro) está recebendo **notificações** (toast, desktop ou badge) de mensagens de outros departamentos (ex.: Comercial, Vendas).

---

## Causa raiz

1. **WebSocket em nível de tenant**  
   Os eventos de chat (`new_message_notification`, `conversation_updated`, `new_conversation`) são enviados para o grupo **`chat_tenant_{tenant_id}`**. Todos os usuários do tenant recebem os mesmos eventos, independentemente do departamento.

2. **Frontend não filtra por permissão**  
   No `useTenantSocket.ts`, ao receber esses eventos o frontend:
   - Atualiza/adiciona a conversa no store
   - Exibe toast e notificação desktop  
   sem verificar se o usuário atual **pode ver** aquela conversa (departamento ou atribuição).

3. **API de departamentos**  
   O `GET /auth/departments/` hoje retorna **todos** os departamentos do tenant (com `pending_count`). O frontend filtra por `departmentIds` para exibir as abas, mas os eventos de WebSocket e a decisão de notificar não usam a mesma regra.

---

## Regra de “usuário pode ver a conversa”

**Fonte de verdade:** espelhar a lógica do backend em `ConversationViewSet.get_queryset()` ([views.py](backend/apps/chat/api/views.py)).

Uma conversa é visível para o usuário se **qualquer** das condições for verdadeira:

1. **`can_access_all_departments`** (vem de `user.permissions` / admin) → vê todas.
2. Caso contrário:
   - Conversa **sem departamento** (Inbox: `department` null/undefined ou `department_id` null), **ou**
   - `conversation.department` (id) está em **`departmentIds`** (departamentos do usuário), **ou**
   - Conversa **atribuída ao usuário** (`conversation.assigned_to === user.id`).

**Edge case:** usuário **sem nenhum departamento** (`departmentIds` vazio): só vê Inbox e conversas atribuídas a ele (igual ao backend).

**Normalização no frontend:** `conversation.department` pode vir como `string` (UUID), `{ id, name }` ou `null`. Extrair sempre o id: `const deptId = typeof conversation.department === 'object' ? conversation.department?.id : conversation.department;`.

---

## Proposta de solução (revisada)

### 1. Frontend – filtrar notificações e store por permissão (obrigatório)

**Arquivo:** `frontend/src/modules/chat/hooks/useTenantSocket.ts`

- **Reutilizar** `usePermissions()`: já expõe `can_access_all_departments`, `departmentIds` e opcionalmente `canAccessDepartment(id)`. O hook é usado em componentes React; dentro do handler do WebSocket (callback) obter valores via `useAuthStore.getState()` e `usePermissions` não está disponível fora de componente — usar **`user`** e **`user.department_ids`** (e `user.permissions?.can_access_all_departments`) do authStore, ou passar `departmentIds`/`can_access_all_departments` para o módulo (ex.: setados no store ou obtidos no mount).
- Criar **`userCanSeeConversation(conversation, user, departmentIds, canAccessAllDepartments)`**:
  - Se `canAccessAllDepartments` → `true`.
  - Senão: se conversa sem departamento (deptId vazio/null) → `true`; se `assigned_to === user.id` → `true`; se `deptId` está em `departmentIds` → `true`; senão `false`.
- **Eventos e pontos de aplicação:**
  - **`new_conversation`:** antes de toast, antes de notificação desktop e antes de qualquer `addConversation`/update no store → checar `userCanSeeConversation`; se `false`, não notificar e não adicionar ao store.
  - **`new_message_notification`:** antes de `updateConversation`, toast e notificação desktop → se não puder ver, não atualizar store e não mostrar toast/desktop.
  - **`conversation_updated`:** quando for **nova no store** (`isNewConversation`), antes de `addConversation` → se não puder ver, não adicionar. Para conversa já existente, pode atualizar (quem já vê continua vendo); opcional: não atualizar se não puder ver para evitar inflar store.
- **Recomendado:** não adicionar/atualizar conversa no store quando o usuário não pode ver. Reduz vazamento de dados e garante que contagens/lista fiquem corretas.

Efeito: usuário só recebe notificação e só “enxerga” no store conversas que tem permissão de ver.

### 2. Backend – filtrar departamentos por usuário (recomendado)

**Arquivo:** `backend/apps/authn/views.py` (DepartmentViewSet)

- Para usuários **não** superuser e **não** com permissão “ver todos os departamentos”: retornar apenas departamentos aos quais o usuário pertence (`user.departments` ou `user.department_ids`), em vez de todos do tenant.
- Manter o cálculo de `pending_count` por departamento como está (aplicado aos departamentos já filtrados).
- **Cache:** o cache atual é por tenant (`cache_key` com `tenant_id`). Para não-admin, o queryset passa a depender do usuário; usar **cache key por usuário** (ex.: `user.id`) para a lista de departamentos, ou não cachear quando a lista for filtrada por usuário. Ajustar `fetch_department_ids` para filtrar por `user.departments` quando aplicável.

Efeito: frontend deixa de receber nomes e `pending_count` de departamentos que o usuário não acessa; badge das abas e segurança ficam consistentes.

### 3. Badge nas abas e badge global

- **Abas:** já usam `filteredDepartments` (por `departmentIds`). Com o item 2, o backend só envia departamentos permitidos e os `pending_count` das abas já ficam corretos.
- **Badge global:** se existir (ex.: ícone “Chat” na sidebar com total de não lidas), calcular **somente** sobre conversas que passam em `userCanSeeConversation` (ex.: somar `unread_count` das conversas do store que o usuário pode ver). Hoje o Layout não exibe número no item Chat; se for adicionado no futuro, usar essa regra.

### 4. Ordem de implementação

1. **Primeiro:** item 1 (frontend) — resolve notificação e store sem depender do backend.
2. **Depois:** item 2 (backend) — evita vazamento de dados na API de departamentos e alinha badge às permissões na origem.

---

## Resumo

| Onde | O que fazer |
|------|-------------|
| **useTenantSocket** | Implementar `userCanSeeConversation` (espelhando backend). Em `new_conversation`, `new_message_notification` e em `conversation_updated` (quando adiciona ao store): antes de toast, desktop e add/update no store, checar; se não puder ver, não notificar e não colocar no store. |
| **GET /auth/departments/** | Para não-admin: retornar apenas `user.departments`; ajustar cache key ou não cachear por usuário. |
| **Badge global** (se existir) | Calcular apenas sobre conversas que passam em `userCanSeeConversation`. |

Com isso, badge e notificações passam a respeitar permissão por departamento (e atribuição), sem alterar o broadcast por tenant no WebSocket.

---

## Riscos e conflitos (evitar quebra)

### 1. **Evento `message_received` (não só `new_message_notification`)**

No `useTenantSocket` o handler de **`message_received`** também faz `addConversation(data.conversation)` quando a conversa ainda não está no store (race com `conversation_updated`) e pode chamar `setActiveConversation(data.conversation)` se o usuário está no chat sem conversa ativa.  
**Risco:** adicionar conversa que o usuário não pode ver e até defini-la como ativa.  
**Cuidado:** aplicar `userCanSeeConversation` **também** nesse bloco antes de `addConversation` e antes de `setActiveConversation`. Se não puder ver: não adicionar e não setar como ativa.

### 2. **`updateConversation` em conversas já existentes no store**

Se deixarmos de chamar `updateConversation` quando o usuário “não pode ver”, conversas que **já estão no store** (ex.: eram atribuídas a ele e depois transferidas) podem ficar com dados desatualizados (ex.: `unread_count`, `last_message`).  
**Recomendação:** bloquear apenas **adição** (addConversation) quando não pode ver. Para **atualização** (updateConversation), se a conversa já está no store, continuar atualizando. Assim não se adiciona conversa “invisível” e não se deixa conversa já visível ficar obsoleta.

### 3. **Comparação `assigned_to === user.id` (tipo)**

No frontend, `Conversation.assigned_to` pode vir como string (UUID ou id) e `user.id` no authStore está tipado como `number`.  
**Cuidado:** usar comparação segura, ex.: `String(conversation.assigned_to) === String(user?.id)` (ou normalizar ambos para string antes de comparar), para não quebrar quando os tipos forem diferentes.

### 4. **Backend: quem precisa da lista completa de departamentos**

Vários pontos usam `GET /auth/departments/`: DepartmentTabs, TransferModal, ConfigurationsPage, WelcomeMenuPage, UsersManager, DepartmentsManager, etc. **Admin** (e quem “pode ver todos os departamentos”) precisa da lista **completa** do tenant para dropdowns e configurações.  
**Cuidado no backend:** filtrar por `user.departments` **apenas** quando o usuário **não** for admin (ex.: `not user.can_access_all_departments()`). Para admin, manter o comportamento atual (todos os departamentos do tenant). Assim evita quebra em Configurations, UsersManager, TransferModal para admin.

### 5. **Cache do backend (DepartmentViewSet)**

Hoje o cache de departamentos é por **tenant** (`cache_key` com `tenant_id`). Se passarmos a filtrar por usuário, a lista passa a depender do usuário.  
**Cuidado:** para usuários não-admin, usar cache key que inclua o **user.id** (ou não cachear a lista quando for filtrada por usuário). Caso contrário, um agente poderia receber lista de outro agente por causa do cache compartilhado.

### 6. **`user` / `permissions` no handler do WebSocket**

Os handlers do WebSocket são callbacks; não dá para usar o hook `usePermissions()` ali.  
**Cuidado:** ler `user` de `useAuthStore.getState().user` e daí usar `user.department_ids` e `user.permissions?.can_access_all_departments` (ou fallback para `user.is_admin`). Garantir que o login/sessão preencha `user.department_ids` e `user.permissions` para que a checagem funcione assim que o WS conectar.

### 7. **Conversa já no store vinda de outra aba/API**

Se o usuário não adicionar uma conversa ao store por não poder ver (ex.: Comercial), mas depois essa conversa for **atribuída a ele** ou **transferida para um departamento dele**, ela passará a ser visível na API. Na próxima listagem (refetch) ou ao abrir por link, a conversa entrará no store pela API. Não é necessário tratamento extra; só garantir que a regra “pode ver” use sempre os dados atuais (department, assigned_to).

### 8. **useChatSocket (sala por conversa)**

O `useChatSocket` lida com eventos da **sala** de uma conversa específica (após o usuário abrir essa conversa). Quem entra na sala já passou pela lista/API, então em tese já pode ver a conversa. Por consistência, pode-se aplicar a mesma checagem antes de `addConversation`/`updateConversation` no useChatSocket se houver caminho que adicione conversa por lá; não é o foco principal (o problema é o broadcast por tenant no useTenantSocket).
