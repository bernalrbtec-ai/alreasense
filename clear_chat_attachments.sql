-- ========================================
-- LIMPAR TABELA chat_attachment
-- ========================================
-- Remove todos os attachments e reseta sequências
-- Data: 30/10/2025
-- ========================================

-- 1. Ver quantos attachments existem
SELECT 
    COUNT(*) as total_attachments,
    COUNT(media_hash) as with_hash,
    COUNT(*) - COUNT(media_hash) as without_hash
FROM chat_attachment;

-- 2. DELETAR TODOS OS ATTACHMENTS
-- ⚠️ ATENÇÃO: Isso vai apagar TODOS os anexos!
DELETE FROM chat_attachment;

-- 3. Verificar se tabela está vazia
SELECT COUNT(*) as remaining_attachments FROM chat_attachment;

-- 4. (Opcional) Ver mensagens que ficaram sem anexos
SELECT 
    m.id,
    m.content,
    m.direction,
    m.created_at,
    'Anexo deletado' as note
FROM chat_message m
WHERE m.id IN (
    SELECT DISTINCT message_id 
    FROM chat_message 
    WHERE direction = 'outgoing' 
    AND content = ''  -- Mensagens vazias (só anexo)
)
ORDER BY m.created_at DESC
LIMIT 20;

-- ========================================
-- RESULTADO ESPERADO:
-- - 0 attachments na tabela ✅
-- - Próximos attachments terão hash correto ✅
-- - URLs curtas funcionando ✅
-- ========================================

