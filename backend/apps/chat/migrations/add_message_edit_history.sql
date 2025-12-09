-- Migration: Adicionar tabela de histórico de edições de mensagens
-- Data: 2025-12-09
-- Descrição: Tabela para armazenar histórico de edições de mensagens enviadas
-- ✅ CORREÇÃO: Garantir que old_content e new_content sejam nullable (podem estar vazios)

-- Criar tabela se não existir
CREATE TABLE IF NOT EXISTS chat_messageedithistory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
    old_content TEXT,  -- ✅ CORREÇÃO: Nullable (pode estar vazio)
    new_content TEXT,   -- ✅ CORREÇÃO: Nullable (pode estar vazio)
    edited_by_id INTEGER REFERENCES authn_user(id) ON DELETE SET NULL,
    edited_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    evolution_message_id VARCHAR(255),
    metadata JSONB NOT NULL DEFAULT '{}',
    CONSTRAINT chat_messageedithistory_message_id_fkey FOREIGN KEY (message_id) REFERENCES chat_message(id) ON DELETE CASCADE
);

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

