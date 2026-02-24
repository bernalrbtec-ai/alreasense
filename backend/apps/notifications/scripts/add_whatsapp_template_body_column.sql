-- Adiciona coluna body em notifications_whatsapp_template (idempotente).
-- Executar uma vez: psql $DATABASE_URL -f add_whatsapp_template_body_column.sql
-- Ou no Railway: railway run psql $DATABASE_URL -f backend/apps/notifications/scripts/add_whatsapp_template_body_column.sql

ALTER TABLE notifications_whatsapp_template
ADD COLUMN IF NOT EXISTS body TEXT NOT NULL DEFAULT '';
