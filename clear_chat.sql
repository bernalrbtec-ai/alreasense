-- 🗑️ Limpar todo o histórico do chat
-- Execute este SQL no Railway Database

-- 1. Ver o que existe
SELECT 'ANTES da limpeza' as momento,
       COUNT(*) as total_conversas
FROM chat_conversation;

SELECT 'ANTES da limpeza' as momento,
       COUNT(*) as total_mensagens
FROM chat_message;

-- 2. Deletar mensagens primeiro (FK para conversas)
DELETE FROM chat_message;

-- 3. Deletar conversas
DELETE FROM chat_conversation;

-- 4. Verificar resultado
SELECT 'DEPOIS da limpeza' as momento,
       COUNT(*) as total_conversas
FROM chat_conversation;

SELECT 'DEPOIS da limpeza' as momento,
       COUNT(*) as total_mensagens
FROM chat_message;

-- ✅ Pronto! Chat zerado.
