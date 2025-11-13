-- ============================================
-- Script SQL: Adicionar suporte a reações externas (WhatsApp)
-- ============================================
-- Este script adiciona o campo external_sender ao modelo MessageReaction
-- para permitir que reações de contatos externos (WhatsApp) sejam salvas no banco
--
-- Data: 2025-11-13
-- Migration equivalente: 0012_add_external_sender_to_reactions.py
-- ============================================

BEGIN;

-- 1. Tornar campo user nullable (para permitir reações de contatos externos)
ALTER TABLE chat_message_reaction 
    ALTER COLUMN user_id DROP NOT NULL;

-- 2. Adicionar campo external_sender
ALTER TABLE chat_message_reaction 
    ADD COLUMN IF NOT EXISTS external_sender VARCHAR(50) DEFAULT '' NOT NULL;

-- Remover DEFAULT após adicionar (não queremos default, queremos blank)
ALTER TABLE chat_message_reaction 
    ALTER COLUMN external_sender DROP DEFAULT;

-- 3. Remover constraint unique antigo (message_id, user_id, emoji)
DROP INDEX IF EXISTS idx_chat_message_reaction_unique;

-- 4. Adicionar índice para external_sender
CREATE INDEX IF NOT EXISTS idx_chat_message_reaction_external_sender 
    ON chat_message_reaction(external_sender, created_at);

-- 5. Adicionar constraint único para user (quando user_id não é NULL)
CREATE UNIQUE INDEX IF NOT EXISTS unique_user_reaction_per_message_emoji 
    ON chat_message_reaction(message_id, user_id, emoji) 
    WHERE user_id IS NOT NULL;

-- 6. Adicionar constraint único para external_sender (quando external_sender não é vazio)
CREATE UNIQUE INDEX IF NOT EXISTS unique_external_reaction_per_message_emoji 
    ON chat_message_reaction(message_id, external_sender, emoji) 
    WHERE external_sender != '';

-- 7. Adicionar comentário na coluna para documentação
COMMENT ON COLUMN chat_message_reaction.user_id IS 'NULL para reações de contatos externos (WhatsApp)';
COMMENT ON COLUMN chat_message_reaction.external_sender IS 'Número do contato que reagiu (para reações recebidas do WhatsApp)';

COMMIT;

-- ============================================
-- Verificação (opcional - executar após aplicar)
-- ============================================
-- SELECT 
--     column_name, 
--     data_type, 
--     is_nullable,
--     column_default
-- FROM information_schema.columns 
-- WHERE table_name = 'chat_message_reaction' 
-- ORDER BY ordinal_position;
--
-- SELECT 
--     indexname, 
--     indexdef 
-- FROM pg_indexes 
-- WHERE tablename = 'chat_message_reaction';
-- ============================================

