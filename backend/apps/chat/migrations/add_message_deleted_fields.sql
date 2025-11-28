-- Migration 0014: Adicionar campos is_deleted e deleted_at na tabela chat_message
-- Execute este script diretamente no PostgreSQL

BEGIN;

-- 1. Adicionar coluna is_deleted (BOOLEAN com default FALSE e índice)
ALTER TABLE chat_message 
ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Criar índice para is_deleted (para queries rápidas de mensagens apagadas)
CREATE INDEX IF NOT EXISTS chat_message_is_deleted_idx ON chat_message(is_deleted);

-- 3. Adicionar coluna deleted_at (TIMESTAMP nullable)
ALTER TABLE chat_message 
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP NULL;

-- 4. Adicionar comentários nas colunas (opcional, mas útil para documentação)
COMMENT ON COLUMN chat_message.is_deleted IS 'True se mensagem foi apagada no WhatsApp';
COMMENT ON COLUMN chat_message.deleted_at IS 'Timestamp quando mensagem foi apagada';

COMMIT;

-- ✅ Verificação: Verificar se as colunas foram criadas corretamente
-- SELECT column_name, data_type, is_nullable, column_default 
-- FROM information_schema.columns 
-- WHERE table_name = 'chat_message' 
-- AND column_name IN ('is_deleted', 'deleted_at');

