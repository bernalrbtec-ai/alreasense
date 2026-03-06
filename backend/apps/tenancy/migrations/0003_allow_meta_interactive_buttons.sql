-- Feature flag: permite desabilitar mensagens com reply buttons (Meta 24h) por tenant
-- Equivalente à migração 0003_add_allow_meta_interactive_buttons.py

-- PostgreSQL
ALTER TABLE tenancy_tenant
ADD COLUMN IF NOT EXISTS allow_meta_interactive_buttons BOOLEAN NOT NULL DEFAULT true;

COMMENT ON COLUMN tenancy_tenant.allow_meta_interactive_buttons IS
  'Permite envio de mensagens com reply buttons (Meta, janela 24h). Desative para desabilitar a feature por tenant.';
