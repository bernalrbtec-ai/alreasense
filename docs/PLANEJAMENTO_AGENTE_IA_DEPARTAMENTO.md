# Planejamento: Agente IA e vínculo com Departamento

## Contexto atual

- **Departamento** (`authn.Department`): já existe; tem `name`, `tenant`, `color`, `transfer_message` e **`ai_enabled`** (boolean). Usuários (agentes humanos) são vinculados a departamentos via `User.departments` (M2M).
- **Conversa** (`chat.Conversation`): tem `department` (FK, opcional; `null` = Inbox pendente) e `assigned_to` (usuário responsável).
- **IA hoje**: `TenantAiSettings` é **por tenant** (um único webhook, um modelo padrão, sem “agentes” distintos). O gateway de teste envia prompt/model no payload; não há entidade “Agente IA” no banco.

Ou seja: já existe “IA habilitada” por departamento (`ai_enabled`), mas **não existe** um “agente IA” configurável (nome, prompt, modelo) nem vínculo explícito agente ↔ departamento.

---

## Objetivo

- **Criar um Agente IA**: entidade configurável (nome, prompt de sistema, modelo, etc.) que representa um “bot”/persona.
- **Conectar o agente a um (ou mais) departamentos**: definir qual agente IA atende cada departamento (e, no futuro, usar isso no fluxo de produção quando a conversa for daquele departamento).

---

## Opções de desenho

### Opção A – Agente IA como entidade; departamento com FK opcional para “agente padrão”

- **Nova tabela `AiAgent`** (ou `AgentIA`):
  - `tenant` (FK)
  - `name` (ex.: "Bia", "Suporte IA")
  - `system_prompt` (TextField, opcional; se vazio, usa padrão do tenant)
  - `model` (CharField, opcional; se vazio, usa `TenantAiSettings.agent_model`)
  - `is_active` (Boolean, default True)
  - `created_at` / `updated_at`
  - (Futuro: RAG, knowledge_source, etc.)
- **Department**:
  - Novo campo opcional: `default_ai_agent` (FK para `AiAgent`, null=True). Um departamento pode ter no máximo um agente IA “padrão”.
- **Fluxo**: ao decidir responder com IA numa conversa do departamento X, o backend usa `department.default_ai_agent`; se for null, usa o comportamento atual (tenant webhook + modelo padrão).

**Prós:** simples; um departamento = um agente. **Contras:** um mesmo agente (ex.: “Bia”) não pode ser reutilizado em vários departamentos sem duplicar (a menos que permitamos M2M depois).

### Opção B – Agente IA com M2M para departamentos

- **Nova tabela `AiAgent`** (como acima).
- **Vínculo**: `AiAgent.departments` (M2M com `Department`). Um agente pode atender vários departamentos; um departamento pode ter um ou mais agentes (aí precisamos de “agente padrão” por departamento ou regra de escolha).
- **Department**: pode ter um campo `default_ai_agent` (FK para `AiAgent`, null=True) para escolher qual dos agentes vinculados usar por padrão.

**Prós:** reuso do mesmo agente em vários departamentos. **Contras:** um pouco mais de complexidade e UI (escolher agente padrão por departamento).

### Opção C – Só expandir Department (sem entidade Agente)

- Não criar `AiAgent`; em vez disso, em **Department** acrescentar: `ai_system_prompt`, `ai_model` (opcional). O “agente” é implícito: o departamento tem nome + prompt + modelo.
- **Prós:** mínimo de mudança. **Contras:** não há entidade reutilizável; cada departamento tem sua própria “persona” duplicada se quiser a mesma em dois departamentos.

---

## Recomendações

- **Curto prazo:** seguir **Opção A**: criar **`AiAgent`** e em **Department** um FK opcional **`default_ai_agent`**. Isso já permite “criar um agente e conectar a um departamento” e deixa caminho aberto para M2M depois (Opção B) se precisar.
- **Backend:**
  - Modelo `AiAgent` em `apps.ai.models`.
  - Migração para criar a tabela e para adicionar `Department.default_ai_agent` (FK, null=True).
  - CRUD de agentes (listar/criar/editar/excluir) por tenant; só admin/gerente.
  - Na tela/API de departamento: campo para escolher “Agente IA padrão” (opcional).
- **Frontend:**
  - Seção “Agentes IA” em Configurações (ou ao lado de “Agentes” humanos): listar, criar, editar (nome, prompt, modelo, ativo).
  - Na tela de edição de departamento: dropdown “Agente IA (opcional)” com os agentes do tenant.
- **Produção (depois):** quando a conversa for de um departamento que tem `default_ai_agent`, o gateway (ou o n8n) pode receber no payload o `prompt` e o `model` desse agente (e no futuro RAG específico do agente).

---

## Resumo

| Item | Proposta |
|------|----------|
| Nova entidade | `AiAgent`: tenant, name, system_prompt, model, is_active |
| Vínculo com departamento | `Department.default_ai_agent` (FK para AiAgent, opcional) |
| Backend | Model + migração; CRUD de AiAgent; API de departamento com default_ai_agent |
| Frontend | Tela de Agentes IA (CRUD); no departamento, seleção de “Agente IA” |
| Uso em produção | Em fase posterior: ao chamar o gateway para uma conversa, enviar prompt/model do agente do departamento (se existir) |

Se quiser, na próxima etapa dá para detalhar endpoints (URLs, payloads) e telas (fluxos e campos) com base nesse desenho.
