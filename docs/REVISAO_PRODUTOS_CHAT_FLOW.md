# Revisão: Produtos ALREA Chat e Flow

Este documento consolida a revisão das regras de produtos (Chat, Flow) e garante que nada quebre.

---

## Resumo da revisão (estado atual)

| Área | Status | Observação |
|------|--------|------------|
| **Backend – Billing** | OK | Validação Flow→Chat; create/update com cópia de dados, remoção de `id`/`product`; `_validate_flow_requires_chat` trata `product` como objeto ou dict. |
| **Backend – Tenancy** | OK | Instâncias só via produto chat; `get_product_limit` com `PlanProduct.DoesNotExist`; `get_product_api_key` com `except Exception`. |
| **Backend – Authn** | OK | Limite de usuários (Chat) na criação; tenant validado antes do uso. |
| **Backend – Views (limites)** | OK | `chat` = dados de instâncias; `flow` = apenas campanhas (objeto fixo). |
| **Frontend – useUserAccess** | OK | Flow = campanhas; Instances = chat; Contacts/Chat/Agenda/Respostas rápidas alinhados às regras. |
| **Frontend – useTenantLimits** | OK | Interface com `chat`; resposta da API validada antes de `setLimits`. |
| **Frontend – PlansPage** | OK | Flow só no select se Chat no plano; `products` com fallback a array; limite usuários para chat. |
| **Frontend – ConfigurationsPage** | OK | Card e botão de instâncias só com `limits.products.chat`; exibição para ilimitado (X / ∞). |
| **SQL / Modelo** | OK | Colunas `limit_value_secondary` e `limit_unit_secondary` via script em `docs/sql/billing/`; migration 0004 removida. |

Nenhum erro de lint nos arquivos alterados. Uma pequena melhoria foi aplicada na validação `_validate_flow_requires_chat` para tratar `product` como dict (consistente com create/update).

---

## Regras de negócio

| Produto | Escopo | Limitadores | Dependência |
|---------|--------|-------------|-------------|
| **ALREA Chat** | Chat, Respostas rápidas, Agenda, Contatos, Instâncias WhatsApp | Instâncias (`limit_value`/`limit_unit`) e Usuários (`limit_value_secondary`/`limit_unit_secondary`) | — |
| **ALREA Flow** | Apenas Campanhas | Nenhum (apenas campanhas) | Só pode ser incluído em plano que já tenha **Chat** |

- **Chat é o produto "pai":** os limites (instâncias e usuários) vêm sempre do **Chat**. Flow é add-on (apenas campanhas) e só pode ser incluído em plano que já tenha Chat.
- **Instâncias e usuários:** apenas o **Chat** define e concede esses limites no plano; Flow não possui limite de instâncias nem de usuários.

---

## Backend – pontos críticos

### 1. Billing

- **`PlanProduct`** (modelo): `limit_value_secondary`, `limit_unit_secondary` existem no modelo; tabela deve ter as colunas (via SQL em `docs/sql/billing/0004_plan_product_limit_secondary.up.sql`). Migration `0004` foi removida (você rodou o SQL).
- **`PlanCreateUpdateSerializer`**:
  - Validação **Flow exige Chat:** se `plan_products` contiver `flow` e não contiver `chat`, retorna `ValidationError` em `plan_products`.
  - `create()`: usa cópia do `product_data`, trata `product_id` e `product`, e remove `product` antes de criar `PlanProduct` (evita KeyError e campos inválidos).
- **`PlanProductSerializer`**: inclui `limit_value_secondary` e `limit_unit_secondary`.

### 2. Tenancy (limites vêm do Chat, produto pai)

- **`can_create_instance()`**: só considera `has_product('chat')`; limite de instâncias vem do **Chat**. Mensagem quando sem acesso: "Produto ALREA Chat não disponível no seu plano (instâncias WhatsApp)".
- **`get_instance_limit_info()`**: só retorna dados quando `has_product('chat')`; usa sempre o limite de instâncias do produto **Chat**.
- **`can_access_product(product_slug)`**: ter produto **chat** concede acesso a **contacts** e **agenda** (para `require_product('contacts')` / `require_product('agenda')`).
- **Limite de usuários**: usa `get_product_limit('chat', 'users')` (i.e. `limit_value_secondary` do PlanProduct do **Chat**).
- **`get_current_usage(..., 'users')`**: conta usuários do tenant.

### 3. Tenancy views (limites)

- **`/tenants/tenants/limits/`**:
  - **chat:** preenche com `get_instance_limit_info()` (uso/limite de instâncias).
  - **flow:** preenche com objeto fixo `has_access: True`, `unlimited: True`, `message: 'Produto Flow: apenas campanhas'` (sem limite de instâncias).
  - **sense** e **api_public**: inalterados.

### 4. Authn

- **`UserCreateSerializer.create()`**: se o tenant tem produto **chat**, verifica limite de usuários (`get_product_limit('chat', 'users')` e `get_current_usage('chat', 'users')`). Se `current >= limit`, levanta `ValidationError` com mensagem de limite atingido.

### 5. Notifications (criação de instância)

- **Criação de instância WhatsApp**: usa `tenant.can_create_instance()` antes de criar; assim, quem não tem **chat** é barrado com a mensagem correta.

---

## Frontend – pontos críticos

### 1. useUserAccess

- **canAccessFlow()**: apenas `hasProductAccess('flow')` (Flow = só campanhas).
- **canAccessInstances()**: apenas `hasProductAccess('chat')` (instâncias = Chat).
- **canAccessContacts()**: role OU `hasProductAccess('chat')` (sem flow).
- **canAccessCampaigns()**: apenas `hasProductAccess('flow')`.
- **canAccessChat()**: role OU workflow OU chat.
- **canAccessAgenda()**: role OU workflow OU chat.
- **Respostas Rápidas** (`/quick-replies`): mesmo critério do Chat (canAccessChat); menu exibe para quem tem produto **chat** ou **workflow** (e roles).

Nenhum outro componente usa `canAccessFlow`/`canAccessInstances` ainda; quando for usar “instâncias”, usar **canAccessInstances**.

### 2. useTenantLimits

- Interface inclui `products.chat` (has_access, current, limit, unlimited, can_create, message).
- `products.flow` tem `can_create?` opcional (backend envia para flow apenas campanhas).

### 3. PlansPage

- **Flow no select:** opção ALREA Flow só aparece se o plano já tiver ALREA Chat.
- Mensagem: "O ALREA Flow é um add-on do ALREA Chat. Adicione o Chat ao plano para poder incluir o Flow (campanhas)."
- Limite de usuários para produto **chat**: `limit_value_secondary` e `limit_unit_secondary`; ao alterar, define `limit_unit_secondary = 'usuários'`.

### 4. ConfigurationsPage

- Bloco de **Instâncias WhatsApp** e botão **Nova Instância** usam apenas `limits.products.chat`:
  - Card de limite só é exibido quando `limits.products.chat?.has_access`.
  - Exibição: se `unlimited`, mostra "X instâncias (ilimitado)" e "X / ∞"; senão "X de Y instâncias".
  - Botão "Nova Instância" desabilitado quando `limits.products.chat?.has_access && limits.products.chat.can_create === false`.

### 5. BillingPage / ConnectionsPage

- BillingPage exibe produtos do plano (incl. flow/chat); não depende de tenant limits para instâncias.
- ConnectionsPage não usa `limits`; criação de instância é validada no backend.

---

## Scripts de teste atualizados

- **`test_instance_limits.py`**: passou a verificar produto **chat** e limites de instâncias via **chat**.
- **`test_instance_count.py`**: passou a usar `get_current_usage('chat', 'instances')` e `get_instance_limit_info()`.

---

## Checklist de não quebrar

- [x] Plano com Flow e sem Chat → API retorna erro de validação.
- [x] Plano com Chat pode ter Flow; plano com só Flow não é permitido.
- [x] Tenant só com Flow: não vê limite de instâncias na ConfigurationsPage; ao tentar criar instância, o backend retorna mensagem de produto Chat não disponível.
- [x] Tenant com Chat: vê card de instâncias e limite; botão "Nova Instância" respeita `can_create`.
- [x] Criação de usuário com limite de usuários do Chat: bloqueada quando atinge o limite.
- [x] Acesso a contatos/agenda: backend considera `can_access_product('chat')` como acesso a contacts/agenda.
- [x] Create/update de plano com `product_id` ou `product` aninhado: tratado no serializer sem KeyError.

---

## Melhorias aplicadas (evitar erros e problemas)

- **Billing serializers**
  - `create`/`update`: uso de cópia dos dados (`dict(product_data)`), remoção de `product` e `id` antes de criar `PlanProduct` (evita KeyError, mutação e PK indevida).
  - `update`: resolução de `product_id` quando vem `product` (objeto ou dict) para manter o mesmo comportamento do `create`.
  - `_validate_flow_requires_chat`: resolução de `product_id` quando o item traz `product` como objeto ou dict (consistente com create/update).
- **Tenancy**
  - `get_product_limit`: exceção restrita a `PlanProduct.DoesNotExist` (não mascara outros erros).
  - `get_product_api_key`: `except Exception` em vez de `except:` (evita bare except).
- **Authn**
  - Criação de usuário: validação de `tenant` ausente com mensagem clara antes de checar limite de usuários.
- **Frontend**
  - **PlansPage**: `products` tratado com `Array.isArray(products) ? products : []` e tipo `Product` no filter/map; mensagem do Flow só exibida quando `Array.isArray(products)`.
  - **useTenantLimits**: resposta da API validada (`data && typeof data === 'object'`) antes de `setLimits` para evitar estado inválido.

---

## Observação

- `manage.py check` pode falhar por dependência ausente (ex.: `reportlab`); isso é independente das alterações de produtos Chat/Flow.
- Se o banco ainda não tiver as colunas `limit_value_secondary` e `limit_unit_secondary`, rodar `docs/sql/billing/0004_plan_product_limit_secondary.up.sql`.
