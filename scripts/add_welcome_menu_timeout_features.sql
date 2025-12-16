-- =========================================
-- WELCOME MENU TIMEOUT FEATURES
-- Adiciona campos de timeout e tabela de controle
-- =========================================

-- 1. Adicionar campos de timeout no chat_welcome_menu_config
ALTER TABLE chat_welcome_menu_config 
ADD COLUMN IF NOT EXISTS inactivity_timeout_enabled BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE chat_welcome_menu_config 
ADD COLUMN IF NOT EXISTS first_reminder_minutes INTEGER NOT NULL DEFAULT 5;

ALTER TABLE chat_welcome_menu_config 
ADD COLUMN IF NOT EXISTS auto_close_minutes INTEGER NOT NULL DEFAULT 10;

-- Comentários nas colunas
COMMENT ON COLUMN chat_welcome_menu_config.inactivity_timeout_enabled IS 'Fecha conversa automaticamente se cliente não responde';
COMMENT ON COLUMN chat_welcome_menu_config.first_reminder_minutes IS 'Minutos até enviar primeiro lembrete';
COMMENT ON COLUMN chat_welcome_menu_config.auto_close_minutes IS 'Minutos até fechar conversa automaticamente';


-- 2. Criar tabela chat_welcome_menu_timeout
CREATE TABLE IF NOT EXISTS chat_welcome_menu_timeout (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL,
    menu_sent_at TIMESTAMP WITH TIME ZONE NOT NULL,
    reminder_sent BOOLEAN NOT NULL DEFAULT FALSE,
    reminder_sent_at TIMESTAMP WITH TIME ZONE NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Foreign key para conversation
    CONSTRAINT fk_timeout_conversation FOREIGN KEY (conversation_id) 
        REFERENCES chat_conversation(id) ON DELETE CASCADE,
    
    -- Garantir que cada conversa tem no máximo um timeout ativo
    CONSTRAINT uq_timeout_conversation UNIQUE (conversation_id)
);

-- Comentários na tabela
COMMENT ON TABLE chat_welcome_menu_timeout IS 'Rastreia timeouts ativos do menu de boas-vindas para fechamento automático';
COMMENT ON COLUMN chat_welcome_menu_timeout.conversation_id IS 'Conversa que tem timeout ativo';
COMMENT ON COLUMN chat_welcome_menu_timeout.menu_sent_at IS 'Quando o menu foi enviado pela última vez';
COMMENT ON COLUMN chat_welcome_menu_timeout.reminder_sent IS 'Se já enviou o lembrete de 5 minutos';
COMMENT ON COLUMN chat_welcome_menu_timeout.reminder_sent_at IS 'Quando o lembrete foi enviado';
COMMENT ON COLUMN chat_welcome_menu_timeout.is_active IS 'Se o timeout ainda está ativo (desativa se cliente responder)';


-- 3. Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_timeout_active_sent 
    ON chat_welcome_menu_timeout(is_active, menu_sent_at)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_timeout_reminder 
    ON chat_welcome_menu_timeout(reminder_sent, reminder_sent_at)
    WHERE is_active = TRUE AND reminder_sent = FALSE;

CREATE INDEX IF NOT EXISTS idx_timeout_conversation 
    ON chat_welcome_menu_timeout(conversation_id);


-- 4. Verificar estrutura criada
DO $$
BEGIN
    -- Verificar colunas adicionadas
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chat_welcome_menu_config' 
        AND column_name = 'inactivity_timeout_enabled'
    ) THEN
        RAISE NOTICE '✅ Coluna inactivity_timeout_enabled criada com sucesso';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chat_welcome_menu_config' 
        AND column_name = 'first_reminder_minutes'
    ) THEN
        RAISE NOTICE '✅ Coluna first_reminder_minutes criada com sucesso';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chat_welcome_menu_config' 
        AND column_name = 'auto_close_minutes'
    ) THEN
        RAISE NOTICE '✅ Coluna auto_close_minutes criada com sucesso';
    END IF;
    
    -- Verificar tabela criada
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'chat_welcome_menu_timeout'
    ) THEN
        RAISE NOTICE '✅ Tabela chat_welcome_menu_timeout criada com sucesso';
    END IF;
    
    -- Verificar índices
    IF EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_timeout_active_sent'
    ) THEN
        RAISE NOTICE '✅ Índice idx_timeout_active_sent criado com sucesso';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_timeout_reminder'
    ) THEN
        RAISE NOTICE '✅ Índice idx_timeout_reminder criado com sucesso';
    END IF;
    
    RAISE NOTICE '🎉 Script executado com sucesso!';
END $$;


-- 5. (OPCIONAL) Marcar migration como aplicada no Django
-- Descomente as linhas abaixo se quiser registrar no sistema de migrations do Django
/*
INSERT INTO django_migrations (app, name, applied)
VALUES ('chat', '0015_welcome_menu_timeout_features', NOW())
ON CONFLICT DO NOTHING;
*/


-- =========================================
-- RESUMO DO QUE FOI CRIADO:
-- =========================================
-- ✅ 3 colunas adicionadas em chat_welcome_menu_config:
--    - inactivity_timeout_enabled (BOOLEAN, default TRUE)
--    - first_reminder_minutes (INTEGER, default 5)
--    - auto_close_minutes (INTEGER, default 10)
--
-- ✅ Tabela chat_welcome_menu_timeout criada com:
--    - id (UUID, primary key)
--    - conversation_id (UUID, foreign key)
--    - menu_sent_at (TIMESTAMP)
--    - reminder_sent (BOOLEAN)
--    - reminder_sent_at (TIMESTAMP, nullable)
--    - is_active (BOOLEAN)
--    - created_at, updated_at
--
-- ✅ 3 índices criados:
--    - idx_timeout_active_sent (is_active, menu_sent_at)
--    - idx_timeout_reminder (reminder_sent, reminder_sent_at)
--    - idx_timeout_conversation (conversation_id)
-- =========================================

