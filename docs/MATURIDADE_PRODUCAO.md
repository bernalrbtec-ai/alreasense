# Análise de maturidade para produção

Documento de análise do projeto Sense (módulo de chat e aba Grupos) para decisão de ida a produção.  
*Atualizado após implementação de toast/retry, sync de grupos e correção do nome do grupo.*

---

## 1. Resumo executivo

| Área              | Nível   | Observação principal                                      |
|-------------------|--------|-----------------------------------------------------------|
| Segurança backend | ✅ Bom | Tenant + permissões; filtro `conversation_type` seguro; sync_groups por tenant |
| Erro / resiliência| ✅ Bom | ErrorBoundary; toast + "Tentar novamente" na lista; ApiErrorHandler; 401 redirect |
| Testes            | ⚠️ Baixo | Sem testes E2E/frontend; poucos testes no chat           |
| Config / deploy   | ✅ Bom | DEBUG default False; CORS; Railway; build sem console     |
| Feature Grupos    | ✅ Pronto | Aba, listagem, sync, nome correto (placeholder + refresh-info), sem "Fechar conversa" |

**Veredicto:** O projeto está **pronto para produção** do ponto de vista de segurança, configuração, aba Grupos e feedback de erro. O principal ponto a evoluir após o deploy é a **cobertura de testes automatizados** (API e, se possível, E2E).

---

## 2. Segurança

### 2.1 Backend (chat/conversas)

- **Tenant:** `get_queryset()` do `ConversationViewSet` filtra sempre por `tenant=user.tenant` antes de qualquer lógica de departamento. Usuário sem tenant não vê conversas.
- **Permissões:** `CanAccessChat` + filtro por departamentos/atribuição/inbox. Admin vê tudo do tenant; gerente/agente só o permitido.
- **Filtro `conversation_type`:** Incluído em `filterset_fields`; o Django Filter aplica **depois** do `get_queryset()`. Ou seja, `?conversation_type=group` só restringe conversas que o usuário já poderia ver.
- **Endpoints de grupo:** `refresh-info`, `group-info`, `participants` checam `conversation_type == 'group'` e retornam 400 quando não for grupo.
- **sync_groups:** Filtra instâncias por `tenant`; usa `update_or_create` por (tenant, contact_phone=group_jid); resposta da Evolution tratada como lista ou dict com chave `groups`.

### 2.2 Frontend

- API base URL por env (`VITE_API_BASE_URL`) com fallback por host (staging/production).
- Interceptor axios: em 401 remove token e redireciona para `/login`.
- Sem exposição de tokens ou dados sensíveis em logs (em produção o build remove `console`).

### 2.3 Configuração (Django)

- `DEBUG` default `False`.
- `SECRET_KEY` via env (default apenas para build).
- `ALLOWED_HOSTS` configurável; CORS restrito a origens permitidas.

**Recomendação:** Manter `ENABLE_MY_CONVERSATIONS=True` em produção se a aba "Minhas Conversas" (e o fluxo de atribuição) estiver em uso; a aba Grupos não depende dessa flag.

---

## 3. Tratamento de erros e resiliência

### 3.1 O que está implementado

- **ErrorBoundary** em volta da árvore da aplicação (`App.tsx`): captura erros de renderização e exibe tela de fallback com “Voltar ao Dashboard” e “Recarregar”.
- **API:** Interceptor trata 401; `ApiErrorHandler` centraliza mensagens por status (400, 403, 404, 429, 5xx).
- **Backend:** `get_queryset()` em try/except com fallback para `_get_queryset_current_behavior` em caso de exceção.
- **Frontend (Grupos/lista):** Uso de `status ?? 'open'/'pending'`, `conversation_type` opcional e optional chaining evita quebras com payload incompleto.
- **ConversationList – falha de carregamento:** Para primeira carga, “Minhas Conversas” e “Grupos”, em caso de erro: toast com mensagem amigável (`ApiErrorHandler.extractMessage`) e tela inline com mensagem + botão “Tentar novamente” (retry refaz o fetch). Erro de aba só é exibido quando a aba ativa é a que falhou; ao trocar de aba o estado de erro da aba anterior é limpo.

### 3.2 Observações

- **Refresh periódico:** Erro continua silencioso (sem toast), o que é aceitável para atualização em background; a lista pode ficar desatualizada até o próximo retry manual ou nova navegação.

---

## 4. Testes

### 4.1 Estado atual

- **Frontend:** Nenhum arquivo `*.test.ts/tsx` ou `*.spec.ts/tsx` encontrado; em `package.json` não há script `test`.
- **Backend (chat):** Testes em `backend/apps/chat/tests/` (listas interativas, template, 24h, etc.); nenhum teste focado em listagem com `conversation_type=group` ou em permissões da aba Grupos.
- **Integração/E2E:** Nenhum pipeline ou suíte E2E encontrada (ex.: Playwright/Cypress).

### 4.2 Impacto para produção

- Deploy e regressões dependem de **testes manuais** e do comportamento já validado em staging.
- A aba Grupos reutiliza a mesma API e permissões já usadas no resto do chat; o risco é médio, mas qualquer mudança futura em `get_queryset` ou filtros pode afetar grupos sem cobertura automática.

**Recomendação (curto prazo):**  
- Incluir no checklist de release: “Aba Grupos: listar grupos, trocar de aba, não exibir ‘Fechar conversa’ em grupo”.  
**Recomendação (médio prazo):**  
- Adicionar pelo menos um teste de API (ex.: `GET /chat/conversations/?conversation_type=group`) com usuário autenticado e verificação de tenant/permissão; e, se possível, um teste E2E mínimo para o fluxo do chat.

---

## 5. Configuração e deploy

### 5.1 Build e ambiente

- **Vite:** `build` com `drop: ['console', 'debugger']` — logs não vazam em produção.
- **API/WS:** `VITE_API_BASE_URL` e `VITE_WS_BASE_URL`/`VITE_WS_URL`; fallback por host para domínios Railway.
- **Railway:** Presença de `railway.frontend.json` e `railway.backend.json`; backend com Dockerfile.

### 5.2 Variáveis críticas (produção)

- Backend: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `ENABLE_MY_CONVERSATIONS` (se usar Minhas Conversas), CORS, Redis, DB.
- Frontend: `VITE_API_BASE_URL` (e WS se diferente do mesmo host).

Nenhuma variável específica é obrigatória só para a **aba Grupos**; o filtro `conversation_type` é opcional na API.

---

## 6. Feature: aba Grupos

### 6.1 Implementação atual

- **Backend:** `conversation_type` em `filterset_fields`; action `POST /chat/conversations/sync-groups/` (fetchAllGroups + update_or_create por grupo); webhook grava placeholder "Grupo WhatsApp" para grupos (nome real vem do refresh-info).
- **Frontend:** Aba “Grupos” após “Minhas Conversas”; busca e “+” ocultos na aba Grupos; empty state com texto explicativo e botão “Sincronizar grupos da instância”; listagem e contadores excluem/incluem grupos conforme a aba; “Fechar conversa” oculto para grupos no ChatWindow.
- **Nome do grupo:** Webhook não usa mais `pushName` (remetente) para `contact_name`/`group_metadata.group_name`; refresh-info preenche o nome real (subject). ChatWindow só considera “nome real” do grupo quando há `group_metadata.group_name` e participantes ou `participants_updated_at`, evitando pular o refresh quando o nome ainda é placeholder ou do remetente.

### 6.2 Compatibilidade

- Backend: clientes que não enviam `conversation_type` mantêm o comportamento anterior.
- Frontend: `conversation_type` e `status` opcionais; aba Grupos não quebra quando a API não envia esses campos.

### 6.3 Rollback

- **Backend:** Remover `conversation_type` de `filterset_fields` e a action `sync_groups`; reverter em webhooks o uso de placeholder para grupos (opcional).
- **Frontend:** Remover tab “Grupos”, fetch por `conversation_type: 'group'`, botão de sync e lógica de ocultar busca/"+"/"Fechar conversa" para grupos.

Não há feature flag; rollback é via deploy reverso.

---

## 7. Checklist pré-produção (recomendado)

- [ ] **Env:** `DEBUG=False`, `SECRET_KEY` e `ALLOWED_HOSTS` corretos no ambiente de produção.
- [ ] **CORS:** Origens do front de produção listadas em `CORS_ALLOWED_ORIGINS` (ou via env).
- [ ] **ENABLE_MY_CONVERSATIONS:** Definido conforme uso da aba “Minhas Conversas”.
- [ ] **Commit/deploy:** Garantir que todas as alterações de chat (views, webhooks, ConversationList, DepartmentTabs, ChatWindow) estão commitadas e no branch que será implantado.
- [ ] **Manual (aba Grupos):** Listar grupos; trocar entre Inbox / Minhas Conversas / Grupos; abrir um grupo e verificar nome do grupo (não nome do remetente); confirmar que “Fechar conversa” não aparece; testar “Sincronizar grupos” com instância que tem grupos; testar com usuário sem grupos.
- [ ] **Manual (erro/retry):** Simular falha no carregamento (ex.: backend parado ou rede offline) e validar toast + tela de erro + “Tentar novamente”.
- [ ] **Monitoramento:** Garantir que erros 5xx e 401 são monitorados (logs/APM); ErrorBoundary cobre apenas erros de renderização no cliente.

---

## 8. Conclusão

O projeto está **pronto para produção** do ponto de vista de:

- Segurança (tenant, permissões, sync_groups escopo).
- Configuração (DEBUG, CORS, build sem console).
- Aba Grupos (listagem, sync, nome correto, sem “Fechar conversa”, busca/"+” ocultos).
- Tratamento de erro na lista (toast + “Tentar novamente” para primeira carga e abas).

**Antes do deploy:** cumprir o checklist (env, CORS, commit de todas as alterações, testes manuais da aba Grupos e do fluxo de erro/retry).

**Após o deploy:** evoluir **testes automatizados** (API para `conversation_type=group` e sync_groups; E2E mínimo do chat, se possível).
