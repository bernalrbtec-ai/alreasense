-- Migração: inbox_idle_minutes em ai_tenant_secretary_profile
-- Secretária: tempo máximo no Inbox sem interação (fechar por falta de comunicação)
-- Rodar: psql -U usuario -d banco -f scripts/migrate_inbox_idle_minutes.sql

-- Adicionar coluna (PostgreSQL)
ALTER TABLE ai_tenant_secretary_profile
ADD COLUMN IF NOT EXISTS inbox_idle_minutes INTEGER NOT NULL DEFAULT 0;

-- Opcional: registrar no django_migrations para o Django não tentar aplicar de novo
-- INSERT INTO django_migrations (app, name, applied) VALUES ('ai', '0011_add_inbox_idle_minutes', NOW());
