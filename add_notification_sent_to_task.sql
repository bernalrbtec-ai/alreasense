-- Migration: 0005_add_notification_sent_to_task
-- Adiciona campo notification_sent à tabela contacts_task

-- Adicionar coluna notification_sent
ALTER TABLE contacts_task 
ADD COLUMN notification_sent BOOLEAN NOT NULL DEFAULT FALSE;

-- Criar índice para melhor performance nas consultas
CREATE INDEX IF NOT EXISTS contacts_task_notification_sent_idx 
ON contacts_task(notification_sent);

-- Comentário na coluna
COMMENT ON COLUMN contacts_task.notification_sent IS 'Indica se a notificação foi enviada para os usuários';

