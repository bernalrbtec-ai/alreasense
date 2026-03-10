# Script SQL e impacto nos tenants

## 1. Script (aplicar no banco)

### 1.1 Aplicar – adicionar colunas

Arquivo: `docs/sql/billing/0004_plan_product_limit_secondary.up.sql`

```sql
-- PlanProduct: limite secundário (ALREA Chat = instâncias + usuários)
-- Tabela: billing_plan_product
-- Equivalente à migration 0004_plan_product_limit_secondary (use este script em vez de migrations, se preferir)

ALTER TABLE billing_plan_product
  ADD COLUMN IF NOT EXISTS limit_value_secondary INTEGER NULL;

ALTER TABLE billing_plan_product
  ADD COLUMN IF NOT EXISTS limit_unit_secondary VARCHAR(50) NULL;

COMMENT ON COLUMN billing_plan_product.limit_value_secondary IS 'Limite secundário (ex: número de usuários)';
COMMENT ON COLUMN billing_plan_product.limit_unit_secondary IS 'Unidade do limite secundário (ex: usuários)';
```

### 1.2 Reversão – remover colunas (só se precisar desfazer)

Arquivo: `docs/sql/billing/0004_plan_product_limit_secondary.down.sql`

```sql
-- Reversão: remove limite secundário de billing_plan_product

ALTER TABLE billing_plan_product
  DROP COLUMN IF EXISTS limit_value_secondary;

ALTER TABLE billing_plan_product
  DROP COLUMN IF EXISTS limit_unit_secondary;
```

---

## 2. Impacto do script SQL nos outros tenants

O script **só adiciona duas colunas** em `billing_plan_product` com `NULL` permitido.

| Aspecto | Impacto |
|--------|--------|
| **Dados existentes** | Nenhum. Linhas atuais ganham `NULL` nas duas colunas. Nada é apagado nem alterado. |
| **Planos existentes** | Nenhum. Planos e `PlanProduct` continuam iguais; apenas passam a ter duas colunas a mais. |
| **Tenants existentes** | Nenhum efeito direto. Quem define o que o tenant pode fazer é o **plano** (e os produtos do plano), não o script. |
| **Risco de quebra** | Baixo. Se o código novo for deployado **sem** rodar o script, aí sim pode dar erro ao ler/gravar essas colunas. Por isso: **rodar o script antes (ou junto) do deploy do código**. |

Conclusão: **o script em si não muda comportamento de nenhum tenant**. Só prepara o banco para o código que usa limite secundário (ex.: limite de usuários do ALREA Chat).

---

## 3. Impacto da mudança de regras (código novo) nos outros tenants

Aqui o impacto vem da **lógica nova** (Flow = só campanhas; instâncias só com Chat; limite de usuários no Chat), não do script.

### 3.1 Tenant com plano que tem **só o produto Flow** (sem Chat)

| O que muda | Antes | Depois |
|------------|--------|--------|
| **Criar instância WhatsApp** | Permitido (limite vinha do Flow). | **Bloqueado.** Mensagem: "Produto ALREA Chat não disponível no seu plano (instâncias WhatsApp)". |
| **Campanhas** | Continua. | Continua (Flow = apenas campanhas). |
| **Tela Configurações** | Podia ver uso/limite de instâncias (flow). | Não vê mais o card "Instâncias WhatsApp (ALREA Chat)". O botão "Nova Instância" pode aparecer, mas ao clicar o backend nega. |

**Impacto:** Perda da capacidade de **criar novas instâncias** para quem tem só Flow. Quem já tem instâncias criadas continua vendo e usando; só não pode criar mais.

**Recomendação:** Listar esses tenants/planos e decidir: migrar o plano para incluir **Chat** (se devem ter instâncias) ou deixar só Flow (apenas campanhas) e comunicar.

---

### 3.2 Tenant com plano que tem **só o produto Chat** (sem Flow)

O **Chat é o produto "pai"**: os limites (instâncias e usuários) vêm sempre dele.

| O que muda | Antes | Depois |
|------------|--------|--------|
| **Criar instância WhatsApp** | Não se aplicava (antes instâncias eram Flow). | **Permitido**, com limite definido no plano no **Chat** (limit_value/limit_unit). |
| **Campanhas** | Dependia de Flow. | Continua dependendo de **Flow** (Chat não inclui campanhas). |
| **Chat, Agenda, Contatos** | Dependia de workflow/outros. | **Permitido** (Chat unifica). |
| **Limite de usuários** | Não existia. | Se o plano tiver `limit_value_secondary`/`limit_unit_secondary` no **Chat**, **passa a valer** na criação de usuários. |

**Impacto:** Só ganhos de funcionalidade e limites claros (todos vindos do Chat). Nenhum bloqueio novo.

---

### 3.3 Tenant com plano que tem **Flow e Chat**

Como o **Chat é o "pai"**, os limites continuam vindo só dele; o Flow é add-on (campanhas).

| O que muda | Antes | Depois |
|------------|--------|--------|
| **Instâncias** | Limite vinha do Flow (ou Chat, conforme implementação anterior). | Limite vem **sempre do Chat**. Flow não define limite de instâncias. |
| **Usuários** | Não existia. | Limite vem **sempre do Chat** (limit_value_secondary no PlanProduct do Chat). |
| **Campanhas** | Flow + Chat. | Continua apenas pelo **Flow** (Chat não inclui campanhas). |

**Impacto:** Comportamento unificado: instâncias e usuários pelo Chat; Flow só campanhas. Se o plano já tinha limites no Chat, nada piora.

---

### 3.4 Tenant com plano **sem Flow e sem Chat** (ex.: só Sense ou API Pública)

| O que muda | Antes | Depois |
|------------|--------|--------|
| **Instâncias / Campanhas / Chat** | Sem acesso. | Sem acesso (igual). |
| **Limite secundário** | Não usado. | Não usado (colunas NULL). |

**Impacto:** Nenhum.

---

### 3.5 Criação de usuários (qualquer tenant com produto Chat)

| O que muda | Antes | Depois |
|------------|--------|--------|
| **Sem limite de usuários no plano** | Sempre pode criar. | Sempre pode criar (`limit_value_secondary` NULL). |
| **Com limite de usuários no plano** | Não existia. | **Respeitado:** ao atingir o limite, a API retorna erro e não cria o usuário. |

**Impacto:** Só para planos que **tiverem** limite de usuários configurado no produto Chat. Quem não tiver continua ilimitado em usuários.

---

## 4. Resumo do impacto nos outros tenants

| Tipo de tenant | Impacto do script | Impacto das regras novas |
|----------------|-------------------|---------------------------|
| Plano **só Flow** | Nenhum | **Perde** criação de instâncias. |
| Plano **só Chat** | Nenhum | **Ganha** instâncias + limite de usuários (se configurado). Campanhas continuam sendo Flow. |
| Plano **Flow + Chat** | Nenhum | Instâncias/usuários pelo Chat; Flow só campanhas. Sem perda se Chat já tinha limite. |
| Plano **sem Flow e sem Chat** | Nenhum | Nenhum. |

**Único impacto negativo:** tenants cujo plano tem **apenas o produto Flow** deixam de poder **criar novas instâncias**. Recomenda-se identificar esses planos/tenants e decidir se devem ganhar o produto Chat ou seguir só com Flow (campanhas).
