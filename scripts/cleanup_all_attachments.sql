-- ============================================
-- 🗑️ LIMPAR TODOS OS ATTACHMENTS DO BANCO
-- ============================================
-- Este script remove TODOS os attachments do banco de dados.
-- Use com CUIDADO - isso remove TODOS os anexos de TODOS os tenants!
--
-- ⚠️ ATENÇÃO: Execute apenas se quiser limpar TUDO!
-- Para limpar apenas de um tenant específico, use: cleanup_tenant_chat_simple.sql
--
-- Ordem de deleção (respeitando foreign keys):
-- 1. MessageAttachment (tabela: chat_attachment)
-- 2. Mensagens que ficam sem attachments podem ser mantidas ou deletadas separadamente
-- ============================================

-- ✅ 1. Verificar quantos attachments existem
SELECT 
    COUNT(*) as total_attachments,
    COUNT(DISTINCT tenant_id) as total_tenants,
    COUNT(DISTINCT message_id) as total_messages_com_attachments,
    SUM(CASE WHEN storage_type = 's3' THEN 1 ELSE 0 END) as attachments_s3,
    SUM(CASE WHEN storage_type = 'local' THEN 1 ELSE 0 END) as attachments_local,
    SUM(size_bytes) / 1024 / 1024 as total_size_mb
FROM chat_attachment;

-- ✅ 2. Listar attachments recentes (últimos 10)
SELECT 
    id,
    tenant_id,
    message_id,
    original_filename,
    mime_type,
    storage_type,
    media_hash,
    size_bytes,
    created_at
FROM chat_attachment
ORDER BY created_at DESC
LIMIT 10;

-- ✅ 3. DELETAR TODOS OS ATTACHMENTS
-- ⚠️ CUIDADO: Isso remove TUDO! Não tem volta!
DELETE FROM chat_attachment;

-- ✅ 4. Verificar se deletou tudo
SELECT COUNT(*) as remaining_attachments FROM chat_attachment;

-- ✅ 5. (OPCIONAL) Resetar sequência de IDs se necessário
-- Se estiver usando serial/bigserial para IDs:
-- ALTER SEQUENCE chat_attachment_id_seq RESTART WITH 1;

-- ============================================
-- 📋 LOGS ESPERADOS:
-- ============================================
-- Após DELETE FROM chat_attachment:
--   - remaining_attachments deve ser 0
--
-- ============================================
