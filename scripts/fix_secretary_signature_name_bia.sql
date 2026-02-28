-- Define o nome exibido da secretária como "BIA" para todos os tenants.
-- Tabela: ai_tenant_secretary_profile, coluna: signature_name.
-- Execute no banco do Sense (PostgreSQL).

-- Opção 1: Atualizar todos os perfis de secretária
UPDATE ai_tenant_secretary_profile
SET signature_name = 'BIA'
WHERE signature_name IS DISTINCT FROM 'BIA';

-- Opção 2 (alternativa): Atualizar só onde está vazio ou "Secretária IA"
-- UPDATE ai_tenant_secretary_profile
-- SET signature_name = 'BIA'
-- WHERE COALESCE(TRIM(signature_name), '') = '' OR signature_name = 'Secretária IA';

-- Conferir resultado:
-- SELECT id, tenant_id, signature_name FROM ai_tenant_secretary_profile;
