# Maturidade para produção – Fluxo com canvas (arrastar e soltar)

Avaliação da feature **canvas de fluxo com posição persistida, paleta arrastável e conexões pelo Handle** para ir a produção.

---

## 1. Pré-requisitos obrigatórios

### 1.1 Script SQL no banco

- [ ] **Rodar o script SQL** que adiciona as colunas de posição em `chat_flow_node` antes (ou no deploy) do backend:
  ```bash
  psql -f backend/apps/chat/migrations/flow_node_position.sql <conexão>
  ```
  Ou executar no cliente SQL:
  ```sql
  ALTER TABLE chat_flow_node ADD COLUMN IF NOT EXISTS position_x DOUBLE PRECISION NULL;
  ALTER TABLE chat_flow_node ADD COLUMN IF NOT EXISTS position_y DOUBLE PRECISION NULL;
  ```
  - Arquivo: `backend/apps/chat/migrations/flow_node_position.sql`.
  - **Se não rodar:** a API de fluxos pode falhar ao serializar nós (campos inexistentes no banco).

### 1.2 Dependências

- Backend: nenhuma dependência nova além das já usadas pelo projeto.
- Frontend: `@xyflow/react` já está no `package.json`; build e bundle já validados.

---

## 2. Checklist de maturidade

### Backend

| Item | Status |
|------|--------|
| **Autorização** | `FlowViewSet`, `FlowNodeViewSet`, `FlowEdgeViewSet` com `IsAuthenticated` + `IsAdmin`; querysets filtrados por `tenant`. |
| **Tenant em create/update** | `perform_create` em nós e arestas valida que flow/departamento pertencem ao tenant; PATCH de nós usa queryset já filtrado. |
| **Validação de dados** | Serializers validam nome, tipo, body/sections/buttons/media; `FlowEdgeWriteSerializer` valida `to_node` no mesmo fluxo. |
| **Posição** | `position_x`/`position_y` opcionais (null=True); validação de faixa (-1e6 a 1e6) para evitar valores extremos. |
| **Compatibilidade** | Nós existentes sem posição continuam com layout por `order` no frontend; motor de fluxo não depende de posição. |

### Frontend

| Item | Status |
|------|--------|
| **Erros de API** | Toasts com `getApiError(e)` em create/update/delete de fluxo, nó e aresta; PATCH de posição e refetch em caso de erro. |
| **Estado de loading** | `detailLoading` no canvas; `savingNode`, `savingEdge`, `savingFlow`, `deletingId` nos botões/modais. |
| **Fechamento de modal** | `closeNodeForm()` centralizado; `pendingDropPosition` limpo ao fechar/cancelar para não enviar posição indevida. |
| **Conflitos** | Nome único sugerido (`suggestNodeName`); ordem `nextOrder` ao criar por drop; backend `unique_together (flow, name)`. |
| **Conexões** | Self-conexão bloqueada; conexão para nó virtual ignorada; arestas não deletáveis pelo canvas (evita dessinc). |

### Segurança e integridade

| Item | Status |
|------|--------|
| **XSS** | Conteúdo de nós (nome, body_text, etc.) exibido via React; sem `dangerouslySetInnerHTML` no fluxo. |
| **CSRF** | Uso de `api` (axios) com credenciais; backend com restrição de origem conforme projeto. |
| **Integridade** | Arestas validadas (to_node no mesmo fluxo); option_id único por from_node; nome único por fluxo. |

---

## 3. Riscos e mitigações

| Risco | Mitigação |
|-------|------------|
| Script SQL de posição não aplicado | Rodar `flow_node_position.sql` no banco antes do deploy; monitorar erros 500 em `/chat/flows/` e `/chat/flow-nodes/`. |
| Múltiplos PATCH de posição em sequência | Refetch após cada PATCH; assinatura do canvas inclui posição; UI atualiza com dados do servidor. |
| Drop com ref do React Flow ainda null | Fallback (0,0); usuário ajusta no modal ou arrasta o nó depois. |
| Nome duplicado ao criar etapa | Frontend sugere nome único; backend retorna 400 com mensagem de unique_together. |

---

## 4. O que não está coberto (opcional para depois)

| Item | Observação |
|------|------------|
| **Testes automatizados** | Não há testes de API nem de frontend para o fluxo/canvas; cobertura manual ou E2E recomendada no médio prazo. |
| **Desabilitar arraste durante PATCH** | Usuário pode arrastar de novo antes do refetch; não quebra dados, apenas pode haver um PATCH extra. |
| **Logging de auditoria** | Alterações de posição não são logadas em tabela de auditoria; depende do padrão do projeto. |

---

## 5. Conclusão

- **Pronto para produção** desde que o script SQL `flow_node_position.sql` seja aplicado no banco antes (ou no deploy) do backend.
- Backend: autorização, tenant e validação consistentes; posição com faixa limitada.
- Frontend: tratamento de erro, loading e estado do modal alinhados; sem vulnerabilidades óbvias.
- Recomendação: executar `flow_node_position.sql` no pipeline de deploy (ou no banco de staging/produção) e validar em staging com um fluxo existente (sem posição) e um novo (com drop e arraste).
