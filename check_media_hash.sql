-- Verificar se campo media_hash existe e está populado

-- 1. Verificar estrutura da tabela
SELECT 
    column_name, 
    data_type, 
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'chat_attachment' 
AND column_name IN ('id', 'media_hash', 'short_url', 'created_at')
ORDER BY ordinal_position;

-- 2. Verificar attachments recentes (últimos 20)
SELECT 
    id,
    media_hash,
    short_url,
    original_filename,
    mime_type,
    created_at
FROM chat_attachment
ORDER BY created_at DESC
LIMIT 20;

-- 3. Contar attachments com e sem hash
SELECT 
    COUNT(*) as total_attachments,
    COUNT(media_hash) as with_hash,
    COUNT(*) - COUNT(media_hash) as without_hash
FROM chat_attachment;

-- 4. Buscar hash específico que acabou de falhar
SELECT 
    id,
    media_hash,
    short_url,
    original_filename,
    created_at
FROM chat_attachment
WHERE media_hash = '249d4a9a941f'
OR id = (SELECT id FROM chat_attachment ORDER BY created_at DESC LIMIT 1);

