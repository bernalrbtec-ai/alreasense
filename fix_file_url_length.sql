-- ============================================================================
-- FIX: Aumentar tamanho do campo file_url para suportar presigned URLs do S3
-- ============================================================================
-- 
-- PROBLEMA:
-- - Presigned URLs do S3 têm 800-1000 caracteres (com assinatura AWS)
-- - Campo file_url era VARCHAR(500)
-- - Erro: "value too long for type character varying(500)"
-- - Uploads de áudio falhavam ao salvar no banco
--
-- SOLUÇÃO:
-- - Alterar file_url de VARCHAR(500) → TEXT (sem limite)
--
-- SEGURANÇA:
-- - Não perde dados existentes
-- - Operação instantânea (PostgreSQL só muda metadata)
-- - Pode reverter se necessário
--
-- ============================================================================

-- 1. Verificar estado atual do campo
SELECT 
    column_name, 
    data_type, 
    character_maximum_length
FROM information_schema.columns 
WHERE table_name = 'chat_messageattachment' 
AND column_name = 'file_url';

-- 2. Alterar campo para TEXT (sem limite)
ALTER TABLE chat_messageattachment 
ALTER COLUMN file_url TYPE TEXT;

-- 3. Verificar mudança
SELECT 
    column_name, 
    data_type, 
    character_maximum_length as max_length
FROM information_schema.columns 
WHERE table_name = 'chat_messageattachment' 
AND column_name = 'file_url';

-- 4. (Opcional) Ver registros com URLs mais longas
SELECT 
    id,
    LENGTH(file_url) as url_length,
    LEFT(file_url, 80) || '...' as url_preview
FROM chat_messageattachment 
WHERE LENGTH(file_url) > 500
ORDER BY LENGTH(file_url) DESC
LIMIT 5;

-- ============================================================================
-- RESULTADO ESPERADO:
-- - data_type: text
-- - character_maximum_length: NULL (sem limite)
-- ============================================================================

-- PARA REVERTER (se necessário):
-- ALTER TABLE chat_messageattachment ALTER COLUMN file_url TYPE VARCHAR(500);
-- ⚠️  ATENÇÃO: Reverter vai FALHAR se houver URLs > 500 caracteres!












