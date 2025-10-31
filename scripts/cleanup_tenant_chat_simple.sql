-- ============================================================================
-- Script SQL SIMPLES para limpar dados de chat do tenant RBTec Informática
-- 
-- AVISO: Esta operação é IRREVERSÍVEL!
-- Execute este script no PostgreSQL do Railway
-- ============================================================================

-- UUID do tenant RBTec Informática
-- ATENÇÃO: Substitua 'a72fbca7-92cd-4aa0-80cb-1c0a02761218' se necessário

BEGIN;

-- 1. Mostrar estatísticas ANTES da limpeza
SELECT 
    '📊 ANTES - Conversas: ' || COUNT(*)::text as estatistica
FROM chat_conversation
WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218'

UNION ALL

SELECT 
    '📊 ANTES - Mensagens: ' || COUNT(*)::text as estatistica
FROM chat_message m
INNER JOIN chat_conversation c ON m.conversation_id = c.id
WHERE c.tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218'

UNION ALL

SELECT 
    '📊 ANTES - Anexos: ' || COUNT(*)::text as estatistica
FROM chat_attachment
WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';

-- 2. Deletar anexos (primeiro devido à foreign key)
DELETE FROM chat_attachment
WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';

SELECT '✅ Anexos deletados' as resultado;

-- 3. Deletar mensagens
DELETE FROM chat_message
WHERE conversation_id IN (
    SELECT id FROM chat_conversation WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218'
);

SELECT '✅ Mensagens deletadas' as resultado;

-- 4. Deletar conversas
DELETE FROM chat_conversation
WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';

SELECT '✅ Conversas deletadas' as resultado;

-- 5. Mostrar estatísticas DEPOIS da limpeza
SELECT 
    '📊 DEPOIS - Conversas: ' || COUNT(*)::text as estatistica
FROM chat_conversation
WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218'

UNION ALL

SELECT 
    '📊 DEPOIS - Mensagens: ' || COUNT(*)::text as estatistica
FROM chat_message m
INNER JOIN chat_conversation c ON m.conversation_id = c.id
WHERE c.tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218'

UNION ALL

SELECT 
    '📊 DEPOIS - Anexos: ' || COUNT(*)::text as estatistica
FROM chat_attachment
WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';

-- 6. Confirmar transação
COMMIT;

SELECT '✅ LIMPEZA CONCLUÍDA!' as resultado;

-- ============================================================================
-- NOTA IMPORTANTE:
-- Este script SQL NÃO deleta arquivos do S3/MinIO.
-- Os arquivos continuam no bucket, mas não estarão mais referenciados no banco.
-- Para deletar arquivos do S3 também, use o comando Django:
-- python manage.py cleanup_tenant_chat --tenant-id a72fbca7-92cd-4aa0-80cb-1c0a02761218 --clean-s3
-- ============================================================================

