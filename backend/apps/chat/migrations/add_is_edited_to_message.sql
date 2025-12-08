-- Adicionar campos is_edited e updated_at na tabela chat_message
-- Script SQL para rodar direto no banco (sem migrations Django)

-- Adicionar coluna is_edited
ALTER TABLE chat_message 
ADD COLUMN IF NOT EXISTS is_edited BOOLEAN NOT NULL DEFAULT FALSE;

-- Adicionar coluna updated_at (se não existir)
ALTER TABLE chat_message 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Atualizar updated_at para mensagens existentes (usar created_at como base)
UPDATE chat_message 
SET updated_at = created_at 
WHERE updated_at IS NULL;

-- Tornar updated_at NOT NULL após popular
ALTER TABLE chat_message 
ALTER COLUMN updated_at SET NOT NULL;

-- Criar índice para melhorar performance de queries
CREATE INDEX IF NOT EXISTS idx_chat_message_is_edited ON chat_message(is_edited);

-- Comentários nas colunas
COMMENT ON COLUMN chat_message.is_edited IS 'True se mensagem foi editada';
COMMENT ON COLUMN chat_message.updated_at IS 'Timestamp da última atualização da mensagem';

