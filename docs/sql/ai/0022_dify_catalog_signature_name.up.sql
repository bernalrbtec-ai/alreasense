-- Idempotent: adicionar nome de assinatura por agente Dify
-- Usado para exibir assinatura nas mensagens enviadas ao WhatsApp via worker (include_signature + sender_name)

ALTER TABLE IF EXISTS ai_dify_app_catalog
  ADD COLUMN IF NOT EXISTS signature_name VARCHAR(100) NOT NULL DEFAULT '';

