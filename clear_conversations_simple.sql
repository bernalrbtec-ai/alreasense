-- ============================================================
-- SCRIPT SQL SIMPLES - LIMPAR TODAS AS CONVERSAS
-- ============================================================
-- ⚠️  ATENÇÃO: Esta ação é IRREVERSÍVEL!
-- ============================================================

-- Deletar na ordem correta (respeitando foreign keys)
DELETE FROM chat_attachment;
DELETE FROM chat_message;
DELETE FROM chat_conversation;

-- Verificar resultado
SELECT 
    (SELECT COUNT(*) FROM chat_attachment) as anexos_restantes,
    (SELECT COUNT(*) FROM chat_message) as mensagens_restantes,
    (SELECT COUNT(*) FROM chat_conversation) as conversas_restantes;

