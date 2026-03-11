-- Unicidade por (conversation_id, message_id) em vez de message_id global.
-- Permite o mesmo message_id da Evolution em conversas diferentes (duas instâncias/tenants).
-- Rodar manualmente no banco; a migration 0018 foi removida.

-- Garante coluna (idempotente)
ALTER TABLE chat_message ADD COLUMN IF NOT EXISTS message_id VARCHAR(255);

-- Remove unique global em message_id se existir
DROP INDEX IF EXISTS chat_message_message_id_key;
ALTER TABLE chat_message DROP CONSTRAINT IF EXISTS chat_message_message_id_key;

-- Índice único por conversa
CREATE UNIQUE INDEX IF NOT EXISTS uniq_chat_message_conversation_message_id
    ON chat_message (conversation_id, message_id) WHERE message_id IS NOT NULL;
