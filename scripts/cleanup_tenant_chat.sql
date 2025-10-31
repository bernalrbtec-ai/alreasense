-- ============================================================================
-- Script SQL para limpar dados de chat de um tenant específico
-- 
-- USO:
--   1. Substitua 'TENANT_ID_AQUI' pelo UUID do tenant (a72fbca7-92cd-4aa0-80cb-1c0a02761218)
--   2. Execute este script no PostgreSQL
--
-- AVISO: Esta operação é IRREVERSÍVEL!
-- ============================================================================

-- Substituir este UUID pelo ID do tenant RBTec Informática
\set tenant_id 'a72fbca7-92cd-4aa0-80cb-1c0a02761218'

-- ============================================================================
-- 1. ESTATÍSTICAS ANTES DA LIMPEZA
-- ============================================================================

SELECT '📊 ESTATÍSTICAS ANTES DA LIMPEZA' as info;

SELECT 
    'Conversas' as tipo,
    COUNT(*) as total
FROM chat_conversation
WHERE tenant_id = :'tenant_id'

UNION ALL

SELECT 
    'Mensagens' as tipo,
    COUNT(*) as total
FROM chat_message m
INNER JOIN chat_conversation c ON m.conversation_id = c.id
WHERE c.tenant_id = :'tenant_id'

UNION ALL

SELECT 
    'Anexos' as tipo,
    COUNT(*) as total
FROM chat_attachment
WHERE tenant_id = :'tenant_id';

-- ============================================================================
-- 2. DELETAR ANEXOS (PRIMEIRO - devido à foreign key)
-- ============================================================================

BEGIN;

-- Deletar anexos
DELETE FROM chat_attachment
WHERE tenant_id = :'tenant_id';

SELECT '✅ Anexos deletados' as resultado;

-- ============================================================================
-- 3. DELETAR MENSAGENS
-- ============================================================================

DELETE FROM chat_message
WHERE conversation_id IN (
    SELECT id FROM chat_conversation WHERE tenant_id = :'tenant_id'
);

SELECT '✅ Mensagens deletadas' as resultado;

-- ============================================================================
-- 4. DELETAR CONVERSAS
-- ============================================================================

DELETE FROM chat_conversation
WHERE tenant_id = :'tenant_id';

SELECT '✅ Conversas deletadas' as resultado;

-- ============================================================================
-- 5. ESTATÍSTICAS APÓS A LIMPEZA
-- ============================================================================

SELECT '📊 ESTATÍSTICAS APÓS A LIMPEZA' as info;

SELECT 
    'Conversas' as tipo,
    COUNT(*) as total
FROM chat_conversation
WHERE tenant_id = :'tenant_id'

UNION ALL

SELECT 
    'Mensagens' as tipo,
    COUNT(*) as total
FROM chat_message m
INNER JOIN chat_conversation c ON m.conversation_id = c.id
WHERE c.tenant_id = :'tenant_id'

UNION ALL

SELECT 
    'Anexos' as tipo,
    COUNT(*) as total
FROM chat_attachment
WHERE tenant_id = :'tenant_id';

-- Confirmar transação
COMMIT;

SELECT '✅ LIMPEZA CONCLUÍDA!' as resultado;

-- ============================================================================
-- NOTA: Este script SQL NÃO deleta arquivos do S3/MinIO
-- Para deletar arquivos do S3, use o comando Django:
-- python manage.py cleanup_tenant_chat --tenant-id a72fbca7-92cd-4aa0-80cb-1c0a02761218 --clean-s3
-- ============================================================================

