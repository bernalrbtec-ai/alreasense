-- =============================================================================
-- Fluxo: instância WhatsApp para enviar/responder
-- Adiciona whatsapp_instance_id em chat_flow.
-- Idempotente: pode rodar mais de uma vez (ADD COLUMN IF NOT EXISTS).
--
-- Uso: psql $DATABASE_URL -f backend/apps/chat/scripts/flow_whatsapp_instance.sql
-- =============================================================================

ALTER TABLE chat_flow ADD COLUMN IF NOT EXISTS whatsapp_instance_id UUID NULL REFERENCES notifications_whatsapp_instance(id) ON DELETE SET NULL;

COMMENT ON COLUMN chat_flow.whatsapp_instance_id IS 'Quando definida, o fluxo envia e responde por esta instância WhatsApp.';
