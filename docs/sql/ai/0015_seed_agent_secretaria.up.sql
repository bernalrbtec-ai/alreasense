-- Seed: agente padrão Secretária (slug=secretaria, tenant_id=null). Equivalente à migration 0015_seed_agent_secretaria (removida).
-- Rodar após 0014_agent.up.sql: psql $DATABASE_URL -f docs/sql/ai/0015_seed_agent_secretaria.up.sql

SET client_min_messages TO WARNING;

INSERT INTO ai_agent (slug, tenant_id, librechat_agent_id, display_name, system_prompt_override, created_at, updated_at)
SELECT 'secretaria', NULL, '', 'Secretária', '', now(), now()
WHERE NOT EXISTS (
    SELECT 1 FROM ai_agent WHERE slug = 'secretaria' AND tenant_id IS NULL
);
