-- ============================================================================
-- LIMPEZA RÁPIDA DO CHAT - Execute direto no banco
-- ============================================================================

-- Ver ANTES
SELECT 'ANTES' as momento, 
       (SELECT COUNT(*) FROM chat_attachment) as anexos,
       (SELECT COUNT(*) FROM chat_message) as mensagens,
       (SELECT COUNT(*) FROM chat_conversation_participants) as participants,
       (SELECT COUNT(*) FROM chat_conversation) as conversas;

-- LIMPAR TUDO (ordem correta respeitando FK)
DELETE FROM chat_attachment;
DELETE FROM chat_message;
DELETE FROM chat_conversation_participants;
DELETE FROM chat_conversation;

-- Ver DEPOIS
SELECT 'DEPOIS' as momento,
       (SELECT COUNT(*) FROM chat_attachment) as anexos,
       (SELECT COUNT(*) FROM chat_message) as mensagens,
       (SELECT COUNT(*) FROM chat_conversation_participants) as participants,
       (SELECT COUNT(*) FROM chat_conversation) as conversas;

-- ============================================================================
-- PRONTO! ✅
-- ============================================================================

