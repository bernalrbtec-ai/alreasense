-- Dify (fase 1.2): instância WhatsApp opcional por agente
-- Rodar: psql $DATABASE_URL -f docs/sql/ai/0019_dify_catalog_whatsapp_instance.up.sql
--
-- Objetivo:
-- - Permitir amarrar um agente Dify a uma instância WhatsApp específica
-- - Campo opcional; se nulo, usa a instância efetiva da conversa
--
-- Requisitos:
-- - Tabela ai_dify_app_catalog já criada pelo 0017
-- - Tabela notifications_whatsapp_instance existente (ver apps.notifications.models.WhatsAppInstance)

SET client_min_messages TO WARNING;

ALTER TABLE ai_dify_app_catalog
    ADD COLUMN IF NOT EXISTS whatsapp_instance_id UUID NULL REFERENCES notifications_whatsapp_instance(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ai_dify_catalog_tenant_instance_idx
    ON ai_dify_app_catalog (tenant_id, whatsapp_instance_id)
    WHERE whatsapp_instance_id IS NOT NULL;

COMMENT ON COLUMN ai_dify_app_catalog.whatsapp_instance_id IS 'Instância WhatsApp preferencial para este agente Dify (opcional).';

