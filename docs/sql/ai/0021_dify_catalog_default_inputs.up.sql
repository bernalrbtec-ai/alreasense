-- Dify (fase 1.3): inputs padrão por agente
-- Rodar: psql $DATABASE_URL -f docs/sql/ai/0021_dify_catalog_default_inputs.up.sql

SET client_min_messages TO WARNING;

ALTER TABLE ai_dify_app_catalog
    ADD COLUMN IF NOT EXISTS default_inputs JSONB NOT NULL DEFAULT '{}';

COMMENT ON COLUMN ai_dify_app_catalog.default_inputs IS
    'Valores padrão dos campos de entrada do agente Dify.
     Suporta variáveis: {{contact_name}}, {{contact_phone}}, {{conversation_id}}, {{department_name}}.
     Schema dos campos disponível em metadata->input_schema (sincronizado via /v1/parameters).';
