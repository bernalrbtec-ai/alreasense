-- ============================================
-- SCRIPT PARA LIMPAR TODO O CHAT
-- ============================================
-- Execute este SQL no Railway Dashboard:
-- 1. Acesse: https://railway.app
-- 2. Projeto → PostgreSQL → Data
-- 3. Cole e execute este SQL
-- ============================================

-- 1️⃣ Deletar anexos de mensagens (se existir a tabela)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'chat_messageattachment') THEN
        DELETE FROM chat_messageattachment;
    END IF;
END $$;

-- 2️⃣ Deletar mensagens
DELETE FROM chat_message;

-- 3️⃣ Deletar conversas  
DELETE FROM chat_conversation;

-- 4️⃣ Verificar contagens (deve retornar 0, 0)
SELECT 
    (SELECT COUNT(*) FROM chat_conversation) as conversas,
    (SELECT COUNT(*) FROM chat_message) as mensagens;

-- ✅ PRONTO! Chat zerado.
-- Agora teste receber uma nova mensagem no WhatsApp.

