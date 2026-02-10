-- Script para verificar dados do form_data da Secretária IA
-- Verifica se os campos 'email' e 'ramo' (business_area) estão sendo salvos

-- 1. Verificar estrutura da tabela
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'ai_tenant_secretary_profile'
ORDER BY ordinal_position;

-- 2. Listar todos os perfis de secretária com resumo do form_data (sem duplicação)
SELECT 
    id,
    tenant_id,
    is_active,
    use_memory,
    signature_name,
    created_at,
    updated_at,
    -- Listar todas as chaves do JSON form_data como array
    array_to_string(ARRAY(SELECT jsonb_object_keys(form_data::jsonb)), ', ') as form_data_keys,
    -- Verificar se tem email
    CASE 
        WHEN form_data::jsonb ? 'email' THEN 'SIM'
        ELSE 'NÃO'
    END as tem_email,
    -- Verificar se tem business_area (ramo)
    CASE 
        WHEN form_data::jsonb ? 'business_area' THEN 'SIM'
        ELSE 'NÃO'
    END as tem_business_area,
    -- Mostrar valores se existirem
    form_data::jsonb->>'email' as email_value,
    form_data::jsonb->>'business_area' as ramo_value,
    -- Mostrar todos os campos do form_data
    form_data
FROM ai_tenant_secretary_profile
ORDER BY updated_at DESC;

-- 3. Verificar especificamente email e ramo (business_area) por tenant (sem duplicação)
SELECT 
    t.id as tenant_id,
    t.name as tenant_name,
    sp.id as profile_id,
    sp.is_active,
    sp.updated_at,
    -- Campos do form_data
    sp.form_data::jsonb->>'company_name' as empresa,
    sp.form_data::jsonb->>'email' as email,
    sp.form_data::jsonb->>'business_area' as ramo_atuacao,
    sp.form_data::jsonb->>'phone' as telefone,
    sp.form_data::jsonb->>'address' as endereco,
    sp.form_data::jsonb->>'mission' as missao,
    sp.form_data::jsonb->>'services' as servicos,
    -- Contar quantos campos tem no form_data
    (SELECT COUNT(*) FROM jsonb_object_keys(sp.form_data::jsonb)) as total_campos,
    -- Listar todas as chaves
    array_to_string(ARRAY(SELECT jsonb_object_keys(sp.form_data::jsonb)), ', ') as campos_existentes,
    -- Mostrar form_data completo
    sp.form_data
FROM ai_tenant_secretary_profile sp
JOIN tenancy_tenant t ON t.id = sp.tenant_id
ORDER BY sp.updated_at DESC;

-- 4. Verificar apenas tenants que têm email ou ramo preenchidos
SELECT 
    t.id as tenant_id,
    t.name as tenant_name,
    sp.form_data::jsonb->>'email' as email,
    sp.form_data::jsonb->>'business_area' as ramo_atuacao,
    sp.form_data::jsonb->>'company_name' as empresa,
    sp.updated_at
FROM ai_tenant_secretary_profile sp
JOIN tenancy_tenant t ON t.id = sp.tenant_id
WHERE 
    (sp.form_data::jsonb ? 'email' AND sp.form_data::jsonb->>'email' IS NOT NULL AND sp.form_data::jsonb->>'email' != '')
    OR 
    (sp.form_data::jsonb ? 'business_area' AND sp.form_data::jsonb->>'business_area' IS NOT NULL AND sp.form_data::jsonb->>'business_area' != '')
ORDER BY sp.updated_at DESC;

-- 5. Verificar tenants que NÃO têm email ou ramo (para identificar o problema) - SEM DUPLICAÇÃO
SELECT 
    t.id as tenant_id,
    t.name as tenant_name,
    sp.id as profile_id,
    sp.is_active,
    -- Verificar quais campos existem (como string separada por vírgula)
    array_to_string(ARRAY(SELECT jsonb_object_keys(sp.form_data::jsonb)), ', ') as campos_existentes,
    -- Verificar se tem email
    CASE 
        WHEN sp.form_data::jsonb ? 'email' THEN 'SIM (' || COALESCE(sp.form_data::jsonb->>'email', 'VAZIO') || ')'
        ELSE 'NÃO'
    END as status_email,
    -- Verificar se tem business_area
    CASE 
        WHEN sp.form_data::jsonb ? 'business_area' THEN 'SIM (' || COALESCE(sp.form_data::jsonb->>'business_area', 'VAZIO') || ')'
        ELSE 'NÃO'
    END as status_ramo,
    sp.form_data,
    sp.updated_at
FROM ai_tenant_secretary_profile sp
JOIN tenancy_tenant t ON t.id = sp.tenant_id
WHERE 
    NOT (sp.form_data::jsonb ? 'email' AND sp.form_data::jsonb->>'email' IS NOT NULL AND sp.form_data::jsonb->>'email' != '')
    OR 
    NOT (sp.form_data::jsonb ? 'business_area' AND sp.form_data::jsonb->>'business_area' IS NOT NULL AND sp.form_data::jsonb->>'business_area' != '')
ORDER BY sp.updated_at DESC;

-- 6. Estatísticas gerais
SELECT 
    COUNT(*) as total_profiles,
    COUNT(CASE WHEN form_data::jsonb ? 'email' AND form_data::jsonb->>'email' IS NOT NULL AND form_data::jsonb->>'email' != '' THEN 1 END) as profiles_com_email,
    COUNT(CASE WHEN form_data::jsonb ? 'business_area' AND form_data::jsonb->>'business_area' IS NOT NULL AND form_data::jsonb->>'business_area' != '' THEN 1 END) as profiles_com_ramo,
    COUNT(CASE WHEN form_data::jsonb ? 'company_name' AND form_data::jsonb->>'company_name' IS NOT NULL AND form_data::jsonb->>'company_name' != '' THEN 1 END) as profiles_com_empresa,
    COUNT(CASE WHEN form_data::jsonb::text = '{}' OR form_data IS NULL THEN 1 END) as profiles_vazios
FROM ai_tenant_secretary_profile;

-- 7. Ver detalhes completos de um tenant específico (substitua o UUID)
-- SELECT 
--     t.id as tenant_id,
--     t.name as tenant_name,
--     sp.*,
--     sp.form_data::jsonb as form_data_json
-- FROM ai_tenant_secretary_profile sp
-- JOIN tenancy_tenant t ON t.id = sp.tenant_id
-- WHERE t.id = 'SEU-UUID-AQUI';
