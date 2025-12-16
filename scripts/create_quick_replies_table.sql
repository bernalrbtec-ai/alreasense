-- Script SQL para criar tabela de Respostas Rápidas
-- Execute este script diretamente no banco de dados PostgreSQL

-- Criar tabela
CREATE TABLE IF NOT EXISTS chat_quickreply (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    title VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50) DEFAULT '',
    use_count INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Foreign keys
    CONSTRAINT fk_quickreply_tenant FOREIGN KEY (tenant_id) 
        REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    CONSTRAINT fk_quickreply_created_by FOREIGN KEY (created_by_id) 
        REFERENCES authn_user(id) ON DELETE SET NULL
);

-- Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_quickreply_tenant_active 
    ON chat_quickreply(tenant_id, is_active);

CREATE INDEX IF NOT EXISTS idx_quickreply_tenant_category_active 
    ON chat_quickreply(tenant_id, category, is_active);

CREATE INDEX IF NOT EXISTS idx_quickreply_use_count 
    ON chat_quickreply(use_count DESC);

-- Comentários nas colunas
COMMENT ON TABLE chat_quickreply IS 'Respostas rápidas para uso no chat';
COMMENT ON COLUMN chat_quickreply.tenant_id IS 'Tenant dono da resposta rápida';
COMMENT ON COLUMN chat_quickreply.title IS 'Título curto da resposta (ex: Boa tarde)';
COMMENT ON COLUMN chat_quickreply.content IS 'Conteúdo completo da resposta';
COMMENT ON COLUMN chat_quickreply.category IS 'Categoria opcional para organização';
COMMENT ON COLUMN chat_quickreply.use_count IS 'Contador de quantas vezes foi usada';
COMMENT ON COLUMN chat_quickreply.is_active IS 'Se a resposta está ativa';
COMMENT ON COLUMN chat_quickreply.created_by_id IS 'Usuário que criou a resposta';

-- Verificar se a tabela foi criada corretamente
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'chat_quickreply'
ORDER BY ordinal_position;

