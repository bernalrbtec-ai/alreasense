-- Adiciona coluna default_whatsapp_instance_id na tabela authn_user (User).
-- Referencia notifications_whatsapp_instance(id). ON DELETE SET NULL: se a instância
-- for removida, o campo do usuário é limpo (null).
--
-- Executar uma vez no banco (ex.: psql ou cliente do PostgreSQL).
-- PostgreSQL:

ALTER TABLE authn_user
  ADD COLUMN IF NOT EXISTS default_whatsapp_instance_id UUID NULL
  REFERENCES notifications_whatsapp_instance(id) ON DELETE SET NULL;

-- Opcional: índice para buscas por usuários que usam uma instância como padrão
-- CREATE INDEX IF NOT EXISTS idx_authn_user_default_wa_instance
--   ON authn_user(default_whatsapp_instance_id) WHERE default_whatsapp_instance_id IS NOT NULL;
