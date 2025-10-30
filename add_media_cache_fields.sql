-- ========================================
-- ADICIONAR CAMPOS DE CACHE DE MÍDIA
-- ========================================
-- Tabela: chat_attachment
-- Campos: media_hash, short_url
-- Data: 30/10/2025
-- ========================================

-- 1. Adicionar coluna media_hash (hash único de 12 caracteres)
ALTER TABLE chat_attachment 
ADD COLUMN IF NOT EXISTS media_hash VARCHAR(32) NULL UNIQUE;

-- 2. Adicionar coluna short_url (URL curta para Evolution API)
ALTER TABLE chat_attachment 
ADD COLUMN IF NOT EXISTS short_url VARCHAR(255) NULL;

-- 3. Criar índice para media_hash (performance)
CREATE INDEX IF NOT EXISTS idx_chat_attachment_media_hash 
ON chat_attachment(media_hash);

-- 4. Verificar se funcionou
SELECT 
    column_name, 
    data_type, 
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'chat_attachment' 
AND column_name IN ('media_hash', 'short_url')
ORDER BY ordinal_position;

-- Resultado esperado:
-- column_name  | data_type        | character_maximum_length | is_nullable
-- -------------|------------------|--------------------------|------------
-- media_hash   | character varying| 32                       | YES
-- short_url    | character varying| 255                      | YES

