-- =====================================================
-- SQL para adicionar campos de histórico e timestamps em Task
-- Sistema de Histórico de Tarefas
-- =====================================================
--
-- Execute este script diretamente no PostgreSQL
--
-- IMPORTANTE:
-- - Este script adiciona campos started_at e cancelled_at na tabela contacts_task
-- - Cria a tabela contacts_task_history para registrar todas as mudanças
-- - Usa IF NOT EXISTS para evitar erros se já existir
-- =====================================================

-- =====================================================
-- 1. ADICIONAR CAMPOS DE TIMESTAMP NA TABELA contacts_task
-- =====================================================

-- Adicionar campo started_at (quando tarefa foi iniciada)
ALTER TABLE contacts_task 
ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE NULL;

COMMENT ON COLUMN contacts_task.started_at IS 'Data/hora em que a tarefa foi iniciada (status mudou para "em andamento")';

-- Adicionar campo cancelled_at (quando tarefa foi cancelada)
ALTER TABLE contacts_task 
ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP WITH TIME ZONE NULL;

COMMENT ON COLUMN contacts_task.cancelled_at IS 'Data/hora em que a tarefa foi cancelada';

-- =====================================================
-- 2. CRIAR TABELA contacts_task_history
-- =====================================================

CREATE TABLE IF NOT EXISTS contacts_task_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL,
    
    -- Tipo de mudança
    change_type VARCHAR(30) NOT NULL,
    
    -- Status anterior e novo (para mudanças de status)
    old_status VARCHAR(20) NULL,
    new_status VARCHAR(20) NULL,
    
    -- Data/hora anterior e nova (para reagendamentos)
    old_due_date TIMESTAMP WITH TIME ZONE NULL,
    new_due_date TIMESTAMP WITH TIME ZONE NULL,
    
    -- Atribuição anterior e nova
    old_assigned_to_id BIGINT NULL,
    new_assigned_to_id BIGINT NULL,
    
    -- Prioridade anterior e nova
    old_priority VARCHAR(20) NULL,
    new_priority VARCHAR(20) NULL,
    
    -- Usuário que fez a mudança
    changed_by_id BIGINT NULL,
    
    -- Descrição da mudança
    description TEXT NULL,
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys
    CONSTRAINT fk_task_history_task
        FOREIGN KEY (task_id)
        REFERENCES contacts_task(id)
        ON DELETE CASCADE,
    
    CONSTRAINT fk_task_history_old_assigned_to
        FOREIGN KEY (old_assigned_to_id)
        REFERENCES authn_user(id)
        ON DELETE SET NULL,
    
    CONSTRAINT fk_task_history_new_assigned_to
        FOREIGN KEY (new_assigned_to_id)
        REFERENCES authn_user(id)
        ON DELETE SET NULL,
    
    CONSTRAINT fk_task_history_changed_by
        FOREIGN KEY (changed_by_id)
        REFERENCES authn_user(id)
        ON DELETE SET NULL,
    
    -- Check constraint para change_type
    CONSTRAINT check_task_history_change_type
        CHECK (change_type IN (
            'status_change',
            'reschedule',
            'assignment',
            'priority_change',
            'description_update'
        ))
);

-- Índices para contacts_task_history
CREATE INDEX IF NOT EXISTS idx_task_history_task_created_at
    ON contacts_task_history(task_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_task_history_task_change_type
    ON contacts_task_history(task_id, change_type);

CREATE INDEX IF NOT EXISTS idx_task_history_changed_by_created_at
    ON contacts_task_history(changed_by_id, created_at DESC)
    WHERE changed_by_id IS NOT NULL;

-- Comentários
COMMENT ON TABLE contacts_task_history IS 
    'Histórico de mudanças de status e reagendamentos de tarefas. Registra todas as alterações para auditoria e rastreabilidade.';

COMMENT ON COLUMN contacts_task_history.change_type IS 
    'Tipo de mudança: status_change, reschedule, assignment, priority_change, description_update';

COMMENT ON COLUMN contacts_task_history.old_status IS 
    'Status anterior da tarefa (para mudanças de status)';

COMMENT ON COLUMN contacts_task_history.new_status IS 
    'Status novo da tarefa (para mudanças de status)';

COMMENT ON COLUMN contacts_task_history.old_due_date IS 
    'Data/hora anterior (para reagendamentos)';

COMMENT ON COLUMN contacts_task_history.new_due_date IS 
    'Data/hora nova (para reagendamentos)';

COMMENT ON COLUMN contacts_task_history.changed_by_id IS 
    'Usuário que fez a mudança';

-- =====================================================
-- 3. VERIFICAÇÃO (opcional - para confirmar criação)
-- =====================================================

-- Descomente para verificar se as colunas foram adicionadas:
-- SELECT
--     column_name,
--     data_type,
--     is_nullable,
--     column_default
-- FROM information_schema.columns
-- WHERE table_name = 'contacts_task'
--     AND column_name IN ('started_at', 'cancelled_at')
-- ORDER BY column_name;

-- Descomente para verificar se a tabela foi criada:
-- SELECT
--     table_name,
--     column_name,
--     data_type,
--     is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'contacts_task_history'
-- ORDER BY ordinal_position;

-- =====================================================
-- FIM DO SCRIPT
-- =====================================================

