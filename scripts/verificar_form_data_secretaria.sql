-- ============================================================
-- Script para verificar o form_data da secretária no banco
-- Tabela: ai_tenant_secretary_profile
-- Campo: form_data (JSONField)
-- ============================================================

-- QUERY PRINCIPAL: Verificar campos email e business_area (ramo)
-- Para o tenant específico dos logs: 8e082a56-32e8-4c1d-9df6-e34975be18ad
SELECT 
    tenant_id,
    -- Verificar se os campos existem
    CASE WHEN form_data::jsonb ? 'email' THEN '✅ SIM' ELSE '❌ NÃO' END as tem_email,
    CASE WHEN form_data::jsonb ? 'business_area' THEN '✅ SIM' ELSE '❌ NÃO' END as tem_business_area,
    -- Valores dos campos
    form_data::jsonb->>'email' as valor_email,
    form_data::jsonb->>'business_area' as valor_business_area,
    -- Todos os campos presentes
    form_data::jsonb->>'company_name' as company_name,
    form_data::jsonb->>'phone' as phone,
    form_data::jsonb->>'address' as address,
    form_data::jsonb->>'mission' as mission,
    form_data::jsonb->>'services' as services,
    -- Listar TODAS as chaves presentes no JSON
    array_to_string(array(
        SELECT jsonb_object_keys(form_data::jsonb)
    ), ', ') as todas_as_chaves,
    -- Form_data completo (JSON)
    form_data,
    is_active,
    updated_at
FROM ai_tenant_secretary_profile
WHERE tenant_id = '8e082a56-32e8-4c1d-9df6-e34975be18ad'
ORDER BY updated_at DESC
LIMIT 1;

-- ============================================================
-- QUERY ALTERNATIVA: Ver form_data formatado (JSON pretty)
-- ============================================================
SELECT 
    tenant_id,
    jsonb_pretty(form_data::jsonb) as form_data_pretty,
    is_active,
    updated_at
FROM ai_tenant_secretary_profile
WHERE tenant_id = '8e082a56-32e8-4c1d-9df6-e34975be18ad'
ORDER BY updated_at DESC
LIMIT 1;

-- ============================================================
-- QUERY PARA TODOS OS TENANTS: Verificar quais têm email/business_area
-- ============================================================
SELECT 
    tenant_id,
    CASE WHEN form_data::jsonb ? 'email' THEN 'SIM' ELSE 'NÃO' END as tem_email,
    CASE WHEN form_data::jsonb ? 'business_area' THEN 'SIM' ELSE 'NÃO' END as tem_business_area,
    form_data::jsonb->>'email' as valor_email,
    form_data::jsonb->>'business_area' as valor_business_area,
    array_to_string(array(
        SELECT jsonb_object_keys(form_data::jsonb)
    ), ', ') as chaves_presentes,
    updated_at
FROM ai_tenant_secretary_profile
ORDER BY updated_at DESC;
