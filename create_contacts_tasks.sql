-- ============================================
-- SQL para criar tabela contacts_task
-- Tarefas e agenda por departamento
-- ============================================

-- Criar tabela
CREATE TABLE IF NOT EXISTS contacts_task (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relacionamentos principais
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES authn_department(id) ON DELETE CASCADE,
    
    -- Campos da tarefa
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    
    -- Data/hora opcional (se preenchido, aparece no calendário)
    due_date TIMESTAMP WITH TIME ZONE,
    
    -- Atendente atribuído (opcional)
    assigned_to_id BIGINT REFERENCES authn_user(id) ON DELETE SET NULL,
    
    -- Quem criou
    created_by_id BIGINT REFERENCES authn_user(id) ON DELETE SET NULL,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Tabela Many-to-Many: Tarefas e Contatos
CREATE TABLE IF NOT EXISTS contacts_task_related_contacts (
    id BIGSERIAL PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES contacts_task(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES contacts_contact(id) ON DELETE CASCADE,
    UNIQUE(task_id, contact_id)
);

-- Índices simples
CREATE INDEX IF NOT EXISTS idx_contacts_task_status ON contacts_task(status);
CREATE INDEX IF NOT EXISTS idx_contacts_task_priority ON contacts_task(priority);
CREATE INDEX IF NOT EXISTS idx_contacts_task_due_date ON contacts_task(due_date);
CREATE INDEX IF NOT EXISTS idx_contacts_task_created_at ON contacts_task(created_at);

-- Índices compostos (definidos no Meta do modelo)
CREATE INDEX IF NOT EXISTS idx_contacts_task_tenant_dept_status 
    ON contacts_task(tenant_id, department_id, status);

CREATE INDEX IF NOT EXISTS idx_contacts_task_tenant_dept_due_date 
    ON contacts_task(tenant_id, department_id, due_date);

CREATE INDEX IF NOT EXISTS idx_contacts_task_assigned_status 
    ON contacts_task(assigned_to_id, status) WHERE assigned_to_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_contacts_task_created_status 
    ON contacts_task(created_by_id, status) WHERE created_by_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_contacts_task_tenant_status_due_date 
    ON contacts_task(tenant_id, status, due_date) WHERE due_date IS NOT NULL;

-- Índices adicionais para performance
CREATE INDEX IF NOT EXISTS idx_contacts_task_tenant ON contacts_task(tenant_id);
CREATE INDEX IF NOT EXISTS idx_contacts_task_department ON contacts_task(department_id);
CREATE INDEX IF NOT EXISTS idx_contacts_task_assigned_to ON contacts_task(assigned_to_id) WHERE assigned_to_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_task_created_by ON contacts_task(created_by_id) WHERE created_by_id IS NOT NULL;

-- Índices para tabela many-to-many
CREATE INDEX IF NOT EXISTS idx_contacts_task_contacts_task ON contacts_task_related_contacts(task_id);
CREATE INDEX IF NOT EXISTS idx_contacts_task_contacts_contact ON contacts_task_related_contacts(contact_id);

-- Constraints para validar valores
ALTER TABLE contacts_task 
    ADD CONSTRAINT check_task_status 
    CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled'));

ALTER TABLE contacts_task 
    ADD CONSTRAINT check_task_priority 
    CHECK (priority IN ('low', 'medium', 'high', 'urgent'));

-- Comentários nas colunas
COMMENT ON TABLE contacts_task IS 'Tarefas e agenda por departamento - permite tarefas simples ou agendadas';
COMMENT ON COLUMN contacts_task.id IS 'UUID primário da tarefa';
COMMENT ON COLUMN contacts_task.tenant_id IS 'FK para o tenant (multi-tenancy)';
COMMENT ON COLUMN contacts_task.department_id IS 'FK para o departamento responsável';
COMMENT ON COLUMN contacts_task.title IS 'Título da tarefa';
COMMENT ON COLUMN contacts_task.description IS 'Descrição detalhada da tarefa (opcional)';
COMMENT ON COLUMN contacts_task.status IS 'Status da tarefa (pending, in_progress, completed, cancelled)';
COMMENT ON COLUMN contacts_task.priority IS 'Prioridade da tarefa (low, medium, high, urgent)';
COMMENT ON COLUMN contacts_task.due_date IS 'Data/hora agendada (opcional - se preenchido, aparece no calendário)';
COMMENT ON COLUMN contacts_task.assigned_to_id IS 'FK para o atendente atribuído (opcional)';
COMMENT ON COLUMN contacts_task.created_by_id IS 'FK para quem criou a tarefa';
COMMENT ON COLUMN contacts_task.created_at IS 'Timestamp de criação';
COMMENT ON COLUMN contacts_task.updated_at IS 'Timestamp de última atualização';
COMMENT ON COLUMN contacts_task.completed_at IS 'Timestamp de conclusão (preenchido quando status = completed)';

COMMENT ON TABLE contacts_task_related_contacts IS 'Tabela many-to-many: relaciona tarefas com contatos';
COMMENT ON COLUMN contacts_task_related_contacts.task_id IS 'FK para a tarefa';
COMMENT ON COLUMN contacts_task_related_contacts.contact_id IS 'FK para o contato relacionado';

-- ✅ Tabela criada com sucesso!
-- Agora você pode usar a API /api/contacts/tasks/

