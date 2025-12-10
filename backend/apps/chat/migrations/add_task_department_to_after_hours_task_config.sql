-- Migration: Adicionar campo task_department em AfterHoursTaskConfig
-- Data: 2025-12-10
-- Descrição: Permite escolher o departamento onde a tarefa automática será criada

-- Adicionar coluna task_department_id (ForeignKey para authn_department)
ALTER TABLE chat_after_hours_task_config
ADD COLUMN IF NOT EXISTS task_department_id UUID REFERENCES authn_department(id) ON DELETE SET NULL;

-- Criar índice para melhor performance em queries
CREATE INDEX IF NOT EXISTS idx_after_hours_task_config_task_department 
ON chat_after_hours_task_config(task_department_id);

-- Comentário na coluna
COMMENT ON COLUMN chat_after_hours_task_config.task_department_id IS 
'Departamento onde a tarefa será criada. Se NULL, usa o departamento da conversa.';

