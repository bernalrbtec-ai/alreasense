-- Script para diagnosticar e corrigir mensagens rápidas não aparecendo
-- Execute este script no banco de dados para verificar o problema

-- 1. Verificar total de mensagens rápidas
SELECT 
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE is_active = true) as ativas,
    COUNT(*) FILTER (WHERE is_active = false) as inativas
FROM chat_quickreply;

-- 2. Verificar por tenant
SELECT 
    t.name as tenant_name,
    COUNT(qr.id) as total,
    COUNT(qr.id) FILTER (WHERE qr.is_active = true) as ativas,
    COUNT(qr.id) FILTER (WHERE qr.is_active = false) as inativas
FROM tenancy_tenant t
LEFT JOIN chat_quickreply qr ON qr.tenant_id = t.id
GROUP BY t.id, t.name
ORDER BY total DESC;

-- 3. Listar mensagens rápidas inativas (que não aparecem na busca)
SELECT 
    qr.id,
    qr.title,
    qr.content,
    qr.is_active,
    t.name as tenant_name,
    qr.created_at
FROM chat_quickreply qr
JOIN tenancy_tenant t ON t.id = qr.tenant_id
WHERE qr.is_active = false
ORDER BY qr.created_at DESC;

-- 4. CORREÇÃO: Ativar todas as mensagens rápidas inativas (descomente para executar)
-- UPDATE chat_quickreply 
-- SET is_active = true 
-- WHERE is_active = false;

-- 5. Verificar se há mensagens sem tenant (não deveria existir)
SELECT COUNT(*) as sem_tenant
FROM chat_quickreply
WHERE tenant_id IS NULL;

-- 6. Verificar estrutura da tabela
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'chat_quickreply'
ORDER BY ordinal_position;

