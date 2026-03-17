-- Dify (fase 1.1): estender catálogo com URL pública, API key criptografada e departamento padrão
-- Rodar: psql $DATABASE_URL -f docs/sql/ai/0018_dify_catalog_crypto.up.sql
--
-- Objetivo:
-- - Permitir cadastrar por agente: nome, descrição, URL pública do app e API key
-- - Opcional: departamento padrão ligado ao agente (sem ainda forçar uso)
-- - Manter compatibilidade com dados existentes (ALTER TABLE com IF NOT EXISTS)
--
-- Observações:
-- - api_key_encrypted será usada via django_cryptography.fields.encrypt no modelo
-- - O backend NUNCA deve devolver a API key em claro na API; apenas flags (has_api_key)

SET client_min_messages TO WARNING;

ALTER TABLE ai_dify_app_catalog
    ADD COLUMN IF NOT EXISTS public_url TEXT NOT NULL DEFAULT '';

ALTER TABLE ai_dify_app_catalog
    ADD COLUMN IF NOT EXISTS api_key_encrypted TEXT NULL;

ALTER TABLE ai_dify_app_catalog
    ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';

ALTER TABLE ai_dify_app_catalog
    ADD COLUMN IF NOT EXISTS default_department_id UUID NULL REFERENCES authn_department(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ai_dify_catalog_tenant_dept_idx
    ON ai_dify_app_catalog (tenant_id, default_department_id)
    WHERE default_department_id IS NOT NULL;

COMMENT ON COLUMN ai_dify_app_catalog.public_url IS 'URL pública do app Dify (ex.: https://dify.example.com/chat/<app_id>).';
COMMENT ON COLUMN ai_dify_app_catalog.api_key_encrypted IS 'API key criptografada via django_cryptography (não expor em claro).';
COMMENT ON COLUMN ai_dify_app_catalog.description IS 'Descrição amigável do agente.';
COMMENT ON COLUMN ai_dify_app_catalog.default_department_id IS 'Departamento padrão sugerido para uso deste agente (opcional).';

