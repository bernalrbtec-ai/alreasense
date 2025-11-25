-- =====================================================
-- SQL para adicionar campos task_type e include_in_notifications
-- Separação de Tarefas e Agenda
-- =====================================================
--
-- Execute este script diretamente no PostgreSQL
--
-- IMPORTANTE:
-- - Adiciona campo task_type para diferenciar tarefas de agenda
-- - Adiciona campo include_in_notifications para toggle de notificações
-- - Usa IF NOT EXISTS para evitar erros se já existir
-- =====================================================

-- =====================================================
-- 1. ADICIONAR CAMPO task_type
-- =====================================================

ALTER TABLE contacts_task 
ADD COLUMN IF NOT EXISTS task_type VARCHAR(10) NOT NULL DEFAULT 'task';

-- Adicionar constraint CHECK para valores válidos
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'check_task_type_valid'
    ) THEN
        ALTER TABLE contacts_task 
        ADD CONSTRAINT check_task_type_valid 
        CHECK (task_type IN ('task', 'agenda'));
    END IF;
END $$;

-- Criar índice para task_type
CREATE INDEX IF NOT EXISTS idx_task_task_type 
    ON contacts_task(task_type);

-- Comentário
COMMENT ON COLUMN contacts_task.task_type IS 
    'Tipo: task (Tarefa - pendências na tela inicial) ou agenda (Agenda - compromissos no calendário)';

-- =====================================================
-- 2. ADICIONAR CAMPO include_in_notifications
-- =====================================================

ALTER TABLE contacts_task 
ADD COLUMN IF NOT EXISTS include_in_notifications BOOLEAN NOT NULL DEFAULT TRUE;

-- Criar índice para include_in_notifications
CREATE INDEX IF NOT EXISTS idx_task_include_in_notifications 
    ON contacts_task(include_in_notifications);

-- Comentário
COMMENT ON COLUMN contacts_task.include_in_notifications IS 
    'Se desabilitado, esta tarefa/agenda não será incluída nas notificações diárias';

-- =====================================================
-- 3. CRIAR ÍNDICES COMPOSTOS PARA PERFORMANCE
-- =====================================================

-- Índice para queries de notificações (task_type + include_in_notifications)
CREATE INDEX IF NOT EXISTS idx_task_type_notifications 
    ON contacts_task(tenant_id, task_type, include_in_notifications, status)
    WHERE include_in_notifications = TRUE AND task_type = 'task';

-- Índice para queries de agenda (task_type = 'agenda')
CREATE INDEX IF NOT EXISTS idx_task_agenda 
    ON contacts_task(tenant_id, task_type, due_date, status)
    WHERE task_type = 'agenda';

-- =====================================================
-- 4. ATUALIZAR TAREFAS EXISTENTES (OPCIONAL)
-- =====================================================

-- Por padrão, todas as tarefas existentes serão marcadas como 'task' e include_in_notifications = TRUE
-- Se quiser marcar tarefas com due_date como agenda, descomente:
-- UPDATE contacts_task 
-- SET task_type = 'agenda' 
-- WHERE due_date IS NOT NULL AND task_type = 'task';

-- =====================================================
-- 5. VERIFICAÇÃO (opcional - para confirmar criação)
-- =====================================================

-- Descomente para verificar se as colunas foram adicionadas:
-- SELECT
--     column_name,
--     data_type,
--     is_nullable,
--     column_default
-- FROM information_schema.columns
-- WHERE table_name = 'contacts_task'
--     AND column_name IN ('task_type', 'include_in_notifications')
-- ORDER BY column_name;

-- =====================================================
-- FIM DO SCRIPT
-- =====================================================

