-- ========================================
-- VERIFICAR E CORRIGIR INSTANCE NAME
-- ========================================
-- O backend está usando instance_name errado
-- Causando 404 na Evolution API
-- ========================================

-- 1. VER INSTÂNCIAS ATUAIS
SELECT 
    id,
    tenant_id,
    friendly_name,
    instance_name,
    phone_number,
    connection_state
FROM notifications_whatsappinstance
ORDER BY created_at DESC;

-- 2. CORRIGIR INSTANCE NAME (ajustar o UUID conforme necessário)
-- 
-- ⚠️ ATENÇÃO: Substitua os valores corretos antes de executar!
-- 
-- Formato:
-- UPDATE notifications_whatsappinstance
-- SET instance_name = 'cb8cf15c-69db-4d09-95a5-8e00df53f613'
-- WHERE instance_name = '9afdad84-5411-4754-8f63-2599a6b9142c';
-- 
-- Ou, se for pelo tenant:
-- UPDATE notifications_whatsappinstance
-- SET instance_name = 'cb8cf15c-69db-4d09-95a5-8e00df53f613'
-- WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';

-- 3. VERIFICAR SE CORRIGIU
SELECT 
    id,
    friendly_name,
    instance_name,
    phone_number
FROM notifications_whatsappinstance
WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';

