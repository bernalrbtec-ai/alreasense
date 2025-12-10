-- Migration: Marcar todas as mensagens de conversas fechadas como lidas
-- Data: 2025-12-10
-- Descrição: Corrige contador de conversas novas que estava mostrando conversas fechadas não lidas

-- Marcar todas as mensagens incoming (recebidas) de conversas fechadas como 'seen'
-- Isso corrige o unread_count que estava contando mensagens não lidas de conversas já fechadas
UPDATE chat_message
SET status = 'seen'
WHERE conversation_id IN (
    SELECT id FROM chat_conversation WHERE status = 'closed'
)
AND direction = 'incoming'
AND status IN ('sent', 'delivered');  -- Apenas mensagens que ainda não foram marcadas como lidas

-- Log de quantas mensagens foram atualizadas
DO $$
DECLARE
    updated_count INTEGER;
BEGIN
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RAISE NOTICE '✅ Marcadas % mensagens de conversas fechadas como lidas', updated_count;
END $$;

