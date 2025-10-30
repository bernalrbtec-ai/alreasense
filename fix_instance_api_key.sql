-- ========================================
-- LIMPAR API KEY DA INSTÂNCIA
-- ========================================
-- Forçar uso da API key global (EVO_API_KEY do Railway)
-- ao invés da API key incorreta do banco
-- ========================================

-- 1. VER API KEYS ATUAIS
SELECT 
    id,
    friendly_name,
    instance_name,
    api_key,
    phone_number
FROM notifications_whatsapp_instance;

-- 2. LIMPAR API KEY (setar para NULL)
UPDATE notifications_whatsapp_instance
SET api_key = NULL
WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';

-- 3. VERIFICAR SE LIMPOU
SELECT 
    id,
    friendly_name,
    instance_name,
    api_key,
    phone_number
FROM notifications_whatsapp_instance
WHERE tenant_id = 'a72fbca7-92cd-4aa0-80cb-1c0a02761218';

