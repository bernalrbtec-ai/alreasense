-- Campos meta_status e meta_status_updated_at em notifications_whatsapp_template
-- (equivalente à migration 0005_whatsapptemplate_meta_status, para aplicar manualmente)

-- PostgreSQL:
ALTER TABLE notifications_whatsapp_template
  ADD COLUMN IF NOT EXISTS meta_status VARCHAR(20) NULL;

CREATE INDEX IF NOT EXISTS idx_notifications_wa_template_meta_status
  ON notifications_whatsapp_template (meta_status);

ALTER TABLE notifications_whatsapp_template
  ADD COLUMN IF NOT EXISTS meta_status_updated_at TIMESTAMP WITH TIME ZONE NULL;

-- Comentários (opcional, PostgreSQL):
-- COMMENT ON COLUMN notifications_whatsapp_template.meta_status IS 'approved, pending, rejected, limited, disabled, unknown, sync_error';
-- COMMENT ON COLUMN notifications_whatsapp_template.meta_status_updated_at IS 'Última verificação do status na Meta';

-- MySQL (se não usar PostgreSQL):
-- ALTER TABLE notifications_whatsapp_template ADD COLUMN meta_status VARCHAR(20) NULL;
-- CREATE INDEX idx_notifications_wa_template_meta_status ON notifications_whatsapp_template (meta_status);
-- ALTER TABLE notifications_whatsapp_template ADD COLUMN meta_status_updated_at DATETIME(6) NULL;
