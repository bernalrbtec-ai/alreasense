-- Migration: Adicionar tabela de histórico de edições de mensagens
-- Data: 2025-12-09
-- Descrição: Tabela para armazenar histórico de edições de mensagens enviadas
-- ✅ CORREÇÃO: Garantir que old_content e new_content sejam nullable (podem estar vazios)

-- ✅ CORREÇÃO: Criar tabela apenas se não existir (sem constraint inline para evitar conflitos)
DO $$
BEGIN
    -- Criar tabela se não existir
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'chat_messageedithistory') THEN
        CREATE TABLE chat_messageedithistory (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            message_id UUID NOT NULL,
            old_content TEXT,  -- ✅ CORREÇÃO: Nullable (pode estar vazio)
            new_content TEXT,   -- ✅ CORREÇÃO: Nullable (pode estar vazio)
            edited_by_id INTEGER,
            edited_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            evolution_message_id VARCHAR(255),
            metadata JSONB NOT NULL DEFAULT '{}'
        );
        
        -- Adicionar constraint de foreign key apenas se não existir
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint 
            WHERE conname = 'chat_messageedithistory_message_id_fkey'
        ) THEN
            ALTER TABLE chat_messageedithistory 
            ADD CONSTRAINT chat_messageedithistory_message_id_fkey 
            FOREIGN KEY (message_id) REFERENCES chat_message(id) ON DELETE CASCADE;
        END IF;
        
        -- Adicionar constraint de foreign key para edited_by_id apenas se não existir
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint 
            WHERE conname = 'chat_messageedithistory_edited_by_id_fkey'
        ) THEN
            ALTER TABLE chat_messageedithistory 
            ADD CONSTRAINT chat_messageedithistory_edited_by_id_fkey 
            FOREIGN KEY (edited_by_id) REFERENCES authn_user(id) ON DELETE SET NULL;
        END IF;
    ELSE
        -- ✅ CORREÇÃO: Se tabela já existe, apenas garantir que colunas nullable estejam corretas
        -- Alterar old_content e new_content para nullable se ainda não forem
        ALTER TABLE chat_messageedithistory 
        ALTER COLUMN old_content DROP NOT NULL;
        
        ALTER TABLE chat_messageedithistory 
        ALTER COLUMN new_content DROP NOT NULL;
    END IF;
END $$;

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_chat_messageedithistory_message ON chat_messageedithistory(message_id, edited_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messageedithistory_edited_by ON chat_messageedithistory(edited_by_id, edited_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messageedithistory_edited_at ON chat_messageedithistory(edited_at DESC);

-- Comentários
COMMENT ON TABLE chat_messageedithistory IS 'Histórico de edições de mensagens enviadas';
COMMENT ON COLUMN chat_messageedithistory.message_id IS 'Referência à mensagem editada';
COMMENT ON COLUMN chat_messageedithistory.old_content IS 'Conteúdo antes da edição';
COMMENT ON COLUMN chat_messageedithistory.new_content IS 'Conteúdo após a edição';
COMMENT ON COLUMN chat_messageedithistory.edited_by_id IS 'Usuário que fez a edição';
COMMENT ON COLUMN chat_messageedithistory.edited_at IS 'Data e hora da edição';
COMMENT ON COLUMN chat_messageedithistory.evolution_message_id IS 'ID da mensagem na Evolution API';

