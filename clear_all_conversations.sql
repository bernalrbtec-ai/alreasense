-- ============================================================
-- SCRIPT SQL PARA LIMPAR TODAS AS CONVERSAS DO FLOW CHAT
-- ============================================================
-- ⚠️  ATENÇÃO: Esta ação é IRREVERSÍVEL!
--    Todas as conversas, mensagens e anexos serão DELETADOS.
-- ============================================================

-- 1️⃣ Deletar anexos primeiro (FK para mensagens)
DELETE FROM chat_messageattachment;

-- 2️⃣ Deletar mensagens (FK para conversas)
DELETE FROM chat_message;

-- 3️⃣ Deletar conversas
DELETE FROM chat_conversation;

-- 4️⃣ Verificar se há dados restantes
SELECT 
    'Anexos restantes' as tipo,
    COUNT(*) as quantidade
FROM chat_messageattachment
UNION ALL
SELECT 
    'Mensagens restantes' as tipo,
    COUNT(*) as quantidade
FROM chat_message
UNION ALL
SELECT 
    'Conversas restantes' as tipo,
    COUNT(*) as quantidade
FROM chat_conversation;

-- ✅ Se tudo foi deletado, você verá:
--    tipo                  | quantidade
--    ----------------------|------------
--    Anexos restantes      | 0
--    Mensagens restantes   | 0
--    Conversas restantes   | 0

