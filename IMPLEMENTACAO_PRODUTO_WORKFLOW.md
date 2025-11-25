# 🚀 Implementação do Produto Workflow (Chat + Agenda)

**Data:** 2025-11-25  
**Objetivo:** Criar produto "Workflow" que inclui Chat e Agenda/Tarefas, com controle de acesso baseado em produtos

---

## ✅ Alterações Implementadas

### Backend

#### 1. **Criação do Produto Workflow**
- **Arquivo:** `backend/apps/billing/management/commands/create_workflow_product.py`
- **Função:** Cria produto 'workflow' e adiciona a todos os planos ativos
- **Script SQL alternativo:** `backend/create_workflow_product_sql.sql` (para execução direta no banco)

#### 2. **Aplicação de Controle de Acesso**

**a) ConversationViewSet** (`backend/apps/chat/api/views.py`):
```python
from apps.billing.decorators import require_product

@require_product('workflow')
class ConversationViewSet(DepartmentFilterMixin, viewsets.ModelViewSet):
    # ... código existente ...
```

**b) TaskViewSet** (`backend/apps/contacts/views.py`):
```python
from apps.billing.decorators import require_product

@require_product('workflow')
class TaskViewSet(viewsets.ModelViewSet):
    # ... código existente ...
```

### Frontend

#### 1. **Hook useUserAccess** (`frontend/src/hooks/useUserAccess.ts`)
- Adicionado `canAccessWorkflow()` para verificar acesso ao produto workflow

#### 2. **Menu Lateral** (`frontend/src/components/Layout.tsx`)
- Adicionado produto 'workflow' ao `productMenuItems` com:
  - Chat (`/chat`)
  - Agenda (`/agenda`)
- Ícone Calendar importado do lucide-react
- Suporte para agentes (mostra Chat e Agenda se tiverem acesso)

#### 3. **Página Agenda** (`frontend/src/pages/AgendaPage.tsx`)
- Nova página completa para visualizar e gerenciar tarefas/agenda
- Filtros: status, tipo (task/agenda), prioridade, minhas tarefas, atrasadas
- Cards de estatísticas
- Lista de tarefas com informações detalhadas

#### 4. **Rotas** (`frontend/src/App.tsx`)
- Rota `/agenda` protegida com `ProtectedRoute requiredProduct="workflow"`
- Rota `/chat` atualizada para usar `workflow` em vez de `flow`
- Suporte para agentes

---

## 📋 Como Executar

### 1. Criar Produto no Banco de Dados

**Opção A: Via Django Management Command (recomendado)**
```bash
cd backend
python manage.py create_workflow_product
```

**Opção B: Via SQL direto**
```bash
# Execute o script SQL no banco PostgreSQL
psql -U seu_usuario -d seu_banco -f backend/create_workflow_product_sql.sql
```

### 2. Verificar Produto Criado

```sql
-- Verificar produto
SELECT * FROM billing_product WHERE slug = 'workflow';

-- Verificar planos com workflow
SELECT 
    p.name as plan_name,
    pr.name as product_name,
    pp.is_included
FROM billing_plan_product pp
JOIN billing_plan p ON pp.plan_id = p.id
JOIN billing_product pr ON pp.product_id = pr.id
WHERE pr.slug = 'workflow';
```

### 3. Deploy

```bash
git add .
git commit -m "✨ Produto Workflow: Chat + Agenda com controle de acesso"
git push origin main
```

---

## 🎯 Estrutura do Produto

### Produto: ALREA Workflow
- **Slug:** `workflow`
- **Nome:** ALREA Workflow
- **Descrição:** Chat e Agenda/Tarefas integrados para gestão de atendimento e organização
- **Icon:** 💬
- **Color:** #10B981 (verde)
- **Add-on Price:** R$ 29,90/mês (opcional)
- **Requires UI Access:** Sim

### Funcionalidades Incluídas:
1. **Chat**
   - Conversas WhatsApp
   - Mensagens em tempo real
   - Grupos e menções
   - Anexos e mídia

2. **Agenda/Tarefas**
   - Criação e gestão de tarefas
   - Agenda de compromissos
   - Histórico de mudanças
   - Notificações automáticas
   - Relacionamento com contatos

---

## 🔒 Controle de Acesso

### Backend
- `@require_product('workflow')` aplicado em:
  - `ConversationViewSet` - Todas as operações de conversas
  - `TaskViewSet` - Todas as operações de tarefas/agenda

### Frontend
- `ProtectedRoute requiredProduct="workflow"` aplicado em:
  - `/chat` - Página de chat
  - `/agenda` - Página de agenda/tarefas

### Menu Lateral
- Itens aparecem apenas se tenant tiver produto `workflow` ativo
- Agentes também veem Chat e Agenda se tiverem acesso

---

## 📊 Estrutura de Dados

### PlanProduct
- `is_included: true` - Produto incluído no plano
- `is_addon_available: true` - Pode ser adicionado como add-on
- `limit_value: NULL` - Ilimitado por padrão (pode ser configurado)

### TenantProduct
- Criado automaticamente quando tenant tem plano com workflow
- `is_active: true` - Produto ativo para o tenant

---

## 🧪 Testes

### Verificar Acesso
1. **Tenant com workflow:**
   - ✅ Deve acessar `/chat`
   - ✅ Deve acessar `/agenda`
   - ✅ Deve ver itens no menu lateral

2. **Tenant sem workflow:**
   - ❌ Deve receber 403 ao acessar `/api/chat/conversations/`
   - ❌ Deve receber 403 ao acessar `/api/contacts/tasks/`
   - ❌ Não deve ver itens no menu lateral

### Verificar Menu
1. Abrir aplicação
2. Verificar se aparece "Chat" e "Agenda" no menu lateral
3. Clicar em "Agenda" e verificar se carrega a página

---

## 📝 Notas Importantes

1. **Migração de Dados:**
   - O script adiciona workflow a TODOS os planos ativos automaticamente
   - Tenants existentes terão acesso imediato após execução do script

2. **Compatibilidade:**
   - Chat anteriormente usava `flow` - agora usa `workflow`
   - Tarefas não tinham controle de produto - agora requerem `workflow`

3. **Agentes:**
   - Agentes também precisam ter acesso ao produto workflow
   - Menu lateral mostra Chat e Agenda para agentes com acesso

4. **Limites Futuros:**
   - Atualmente ilimitado (`limit_value: NULL`)
   - Pode ser configurado por plano se necessário (ex: 100 conversas ativas)

---

## 🚀 Próximos Passos (Opcional)

1. **Limites de Produto:**
   - Configurar limites por plano (ex: 50 conversas ativas, 100 tarefas/mês)

2. **Métricas de Uso:**
   - Dashboard mostrando uso do produto workflow

3. **Upgrade/Add-on:**
   - Permitir adicionar workflow como add-on para planos que não incluem

---

**Status:** ✅ Implementado e pronto para deploy  
**Arquivos Modificados:** 8 arquivos  
**Arquivos Criados:** 3 arquivos

