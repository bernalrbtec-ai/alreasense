-- ============================================
-- 🗑️ LIMPAR ATTACHMENTS DE UM TENANT ESPECÍFICO
-- ============================================
-- Este script remove attachments de um tenant específico.
--
-- ⚠️ IMPORTANTE: Substitua 'SEU_TENANT_ID_AQUI' pelo UUID do tenant!
-- ============================================

-- ⚙️ CONFIGURAÇÃO: Defina o tenant_id aqui
\set tenant_id 'SEU_TENANT_ID_AQUI'

-- Ou use uma variável PostgreSQL:
-- DO $$
-- DECLARE
--     v_tenant_id UUID := 'SEU_TENANT_ID_AQUI';
-- BEGIN
--     DELETE FROM chat_attachment WHERE tenant_id = v_tenant_id;
--     RAISE NOTICE 'Attachments deletados para tenant: %', v_tenant_id;
-- END $$;

-- ✅ 1. Verificar quantos attachments do tenant existem
SELECT 
    COUNT(*) as total_attachments,
    COUNT(DISTINCT message_id) as total_messages_com_attachments,
    SUM(CASE WHEN storage_type = 's3' THEN 1 ELSE 0 END) as attachments_s3,
    SUM(CASE WHEN storage_type = 'local' THEN 1 ELSE 0 END) as attachments_local,
    SUM(size_bytes) / 1024 / 1024 as total_size_mb
FROM chat_attachment
WHERE tenant_id = :tenant_id;

-- ✅ 2. Listar attachments do tenant (últimos 10)
SELECT 
    id,
    message_id,
    original_filename,
    mime_type,
    storage_type,
    media_hash,
    file_path,
    size_bytes,
    created_at
FROM chat_attachment
WHERE tenant_id = :tenant_id
ORDER BY created_at DESC
LIMIT 10;

-- ✅ 3. DELETAR ATTACHMENTS DO TENANT
-- ⚠️ CUIDADO: Isso remove todos os attachments do tenant! Não tem volta!
DELETE FROM chat_attachment
WHERE tenant_id = :tenant_id;

-- ✅ 4. Verificar se deletou tudo do tenant
SELECT COUNT(*) as remaining_attachments 
FROM chat_attachment 
WHERE tenant_id = :tenant_id;

-- ✅ 5. Verificar total geral de attachments restantes
SELECT COUNT(*) as total_remaining_attachments FROM chat_attachment;

-- ============================================
-- 📋 EXEMPLO DE USO:
-- ============================================
-- 1. Abrir psql ou pgAdmin
-- 2. Conectar ao banco de dados
-- 3. Substituir 'SEU_TENANT_ID_AQUI' pelo UUID real
-- 4. Executar o script
--
-- Ou usar diretamente:
-- DELETE FROM chat_attachment WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';
-- ============================================
