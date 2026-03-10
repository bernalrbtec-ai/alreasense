# Checklist de produção – Produtos Chat e Flow

Verificação para subir para produção com segurança as mudanças de **ALREA Chat**, **ALREA Flow**, limitadores (instâncias + usuários) e regra Flow = add-on do Chat.

**Regra central:** o **Chat é o produto "pai"** — os limites (instâncias e usuários) vêm sempre do Chat. O Flow é add-on (apenas campanhas) e não define limites.

---

## 1. Pré-requisitos obrigatórios (antes do deploy)

### 1.1 Banco de dados

- [ ] **Rodar o SQL do limite secundário** (se ainda não rodou):
  - Arquivo: `docs/sql/billing/0004_plan_product_limit_secondary.up.sql`
  - Conteúdo: adiciona colunas `limit_value_secondary` e `limit_unit_secondary` na tabela `billing_plan_product`.
  - **Se não rodar:** leitura/gravação de planos com limite de usuários (Chat) pode falhar com erro de coluna inexistente.

```sql
ALTER TABLE billing_plan_product
  ADD COLUMN IF NOT EXISTS limit_value_secondary INTEGER NULL;
ALTER TABLE billing_plan_product
  ADD COLUMN IF NOT EXISTS limit_unit_secondary VARCHAR(50) NULL;
```

- [ ] **Migration 0004 do billing foi removida** – o projeto usa só o script SQL acima. Não é necessário rodar `migrate` para essa alteração.

### 1.2 Produto ALREA Chat no banco

- [ ] **Criar/atualizar o produto Chat** (após o deploy do backend):
  - Comando: `python manage.py create_chat_product`
  - Cria/atualiza o produto com `slug=chat`, nome "ALREA Chat", descrição e ícone.
  - Não adiciona o produto aos planos; isso é feito na tela de Planos (admin) ou por seed.

---

## 2. Compatibilidade e comportamento

### 2.1 Tenants que hoje têm só o produto **Flow** (sem Chat)

- **Comportamento novo:** não poderão mais **criar instâncias WhatsApp** (Flow = apenas campanhas).
- **Frontend:** não verão o card "Instâncias WhatsApp (ALREA Chat)" na Configurações; o botão "Nova Instância" continua visível, mas o backend retorna erro ao tentar criar.
- **Ação recomendada:** antes ou logo após o deploy, definir se esses tenants devem:
  - ser migrados para um plano que inclua **Chat** (para continuar com instâncias), ou
  - permanecer só com Flow (apenas campanhas).

### 2.2 Tenants que já têm plano com **Chat**

- Continuam com limite de instâncias (agora sempre via produto **chat**).
- Se o plano tiver `limit_value_secondary`/`limit_unit_secondary` preenchidos, o limite de **usuários** passa a ser aplicado na criação de usuários.

### 2.3 Planos existentes

- **Edição de planos:** não é possível incluir **Flow** sem incluir **Chat** (validação na API e na tela de Planos).
- Planos que já têm Flow e Chat continuam válidos. Planos só com Flow continuam salvos; a validação só impede *incluir* Flow sem Chat em create/update.

---

## 3. Infraestrutura e código

| Item | Status |
|------|--------|
| **TenantMiddleware** | Ativo em `evosense/settings.py`; `request.tenant` preenchido para usuário autenticado. |
| **Authn (criação de usuário)** | Usa `request.user.tenant`; valida tenant antes de checar limite; mensagem clara se tenant ausente. |
| **Decorators de produto** | Verificam `hasattr(request, 'tenant')` e `request.tenant` antes de usar. |
| **Frontend** | Uso de `limits?.products?.chat` e optional chaining; não quebra se API falhar ou não retornar chat. |
| **Sem migrations Django** | Alteração de schema só via SQL; não há dependência de `migrate` para as colunas do limite secundário. |

---

## 4. Riscos e mitigações

| Risco | Mitigação |
|-------|------------|
| Colunas do limite secundário não existirem | Rodar `0004_plan_product_limit_secondary.up.sql` **antes** do deploy do código. |
| Tenant só com Flow perder criação de instâncias | Comunicar e, se desejado, migrar planos para incluir Chat antes do deploy. |
| Produto Chat não existir no banco | Rodar `create_chat_product` após o deploy; sem isso, nenhum plano poderá usar limite de usuários do Chat até o produto existir. |
| Resposta inesperada da API de limites | Frontend valida `data && typeof data === 'object'` antes de `setLimits`; não quebra a tela. |

---

## 5. Ordem recomendada no deploy

1. **Backup do banco** (recomendado).
2. **Rodar o SQL** `docs/sql/billing/0004_plan_product_limit_secondary.up.sql` no banco de produção.
3. **Deploy do backend** (código novo).
4. **Deploy do frontend** (código novo).
5. **Rodar** `python manage.py create_chat_product` no ambiente de produção (se o produto Chat ainda não existir).
6. **Configurar planos** na tela de Planos (ou seed): incluir ALREA Chat onde fizer sentido e, para Chat, preencher limite de instâncias e de usuários quando aplicável.
7. (Opcional) **Comunicar** tenants que hoje têm só Flow sobre a mudança (instâncias apenas com Chat).

---

## 6. Conclusão

- **Pode ir para produção com segurança** desde que:
  1. O SQL do limite secundário tenha sido aplicado no banco **antes** do deploy.
  2. O comando `create_chat_product` seja executado após o deploy (se o produto Chat ainda não existir).
  3. Tenants que hoje têm só Flow estejam alinhados com a regra (Flow = apenas campanhas; instâncias só com Chat).

- Não há dependências de variáveis de ambiente ou feature flags específicas para essas funcionalidades.
- Os TODOs encontrados no projeto estão em outros módulos (billing cycle, date calculator), não no fluxo Chat/Flow/limitadores aqui revisado.
