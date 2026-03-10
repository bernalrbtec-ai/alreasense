# Revisão final – Chat/Flow (não quebra nada)

**Data:** 2026-03-10 (revisão de garantia)

## Objetivo

Confirmar que as alterações de produtos ALREA Chat e ALREA Flow não quebram nada e que o que já funciona continua funcionando.

---

## O que foi conferido

### 1. Backend – Produtos e limites

- **Instâncias:** `Tenant.can_create_instance()` e `get_instance_limit_info()` usam apenas o produto **chat**. Quem tem só Flow não cria instâncias; quem tem Chat segue com o mesmo comportamento.
- **Usuários:** Limite aplicado em `UserCreateSerializer` apenas quando o tenant tem produto **chat** e `limit_value_secondary` definido; planos sem Chat não são afetados.
- **Campanhas:** `CampaignViewSet` e `CampaignNotificationViewSet` passaram a usar `@require_product('flow')`. API de campanhas e notificações só para quem tem Flow — alinhado ao frontend.
- **Billing:** `PlanCreateUpdateSerializer` valida Flow exige Chat; create/update usam cópia dos dados e tratam `product` como objeto ou dict. Nenhuma regressão identificada.

### 2. Frontend – Menu e rotas

- **Menu Chat:** Chat, Respostas Rápidas, Agenda, Contatos (sem Campanhas). Filtros usam `canAccessChat()`, `canAccessAgenda()`, `canAccessContacts()` conforme definido.
- **Menu Flow:** Contatos, Campanhas. Item Campanhas usa `requiredProduct: 'flow'` → `hasProductAccess('flow')`.
- **Rota /campaigns:** `ProtectedRoute requiredProduct="flow"` → usa `hasProductAccess('flow')`. Acesso a Campanhas só com produto Flow — alinhado ao backend.
- **Configurações:** Bloco “Limites do Plano” (instâncias) só quando `limits?.plan && limits?.products?.chat?.has_access`. Botão “Nova Instância” desabilitado quando Chat tem acesso e `can_create === false`.

### 3. Hooks e acesso

- **useUserAccess:** `canAccessInstances()` e `canAccessCampaigns()` refletem apenas os produtos corretos (chat para instâncias, flow para campanhas). Contatos/Agenda/Chat mantêm a lógica de role/workflow/chat.
- **useTenantLimits:** Interface e uso de `products.chat` conferidos; resposta da API validada antes de `setLimits`.

### 4. Planos (PlansPage)

- Flow só aparece no select se Chat já estiver no plano; validação e mensagem de add-on; `products` com fallback a array.

### 5. Linter e Django

- **Linter:** Sem erros nos arquivos alterados (useUserAccess, Layout, ConfigurationsPage, PlansPage, billing serializers, tenancy, authn).
- **Django check:** Falha no ambiente local por dependência ausente (`reportlab`) no app de campanhas — **não é causada** pelas alterações de billing/tenancy/authn. Em ambiente com dependências instaladas, o check deve passar.

---

## Conclusão

- **Não quebra:** Rotas, APIs, menu, limites e criação de usuários/instâncias estão consistentes com Chat = pai (instâncias e usuários) e Flow = add-on (apenas campanhas).
- **O que já funciona continua:** Quem tem Chat continua com Chat, Respostas rápidas, Agenda, Contatos e Instâncias. Quem tem Flow continua acessando Campanhas. Quem tem só Flow não vê nem cria instâncias (comportamento desejado).
- **Produção:** As alterações são compatíveis com quem já usa; instâncias e usuários existentes não são removidos; único cuidado documentado: plano só com Flow não pode criar novas instâncias (evitar oferecendo Chat no plano).

Revisão concluída: **não quebra nada do que foi alterado e o que está funcionando permanece.**
