-- ========================================
-- VERIFICAR API KEYS DAS INSTÂNCIAS
-- ========================================
-- Checar se tem API keys erradas/antigas
-- ========================================

-- 1. VER TODAS AS INSTÂNCIAS E SUAS API KEYS
SELECT 
    id,
    tenant_id,
    friendly_name,
    instance_name,
    api_key,  -- ⚠️ ESSA PODE ESTAR ERRADA!
    phone_number,
    connection_state,
    created_at
FROM notifications_whatsapp_instance
ORDER BY created_at DESC;

-- 2. LIMPAR API KEY DA INSTÂNCIA (forçar usar a global)
-- UPDATE notifications_whatsapp_instance
-- SET api_key = NULL
-- WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';

-- 3. VERIFICAR SE LIMPOU
-- SELECT id, instance_name, api_key FROM notifications_whatsapp_instance;

