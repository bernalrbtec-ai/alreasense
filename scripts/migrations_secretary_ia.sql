-- Migrações Secretária IA (aplicar direto no PostgreSQL)
-- Corresponde a: ai.0008_secretary_profile_and_indexes + authn.0006_department_routing_keywords

BEGIN;

-- ========== AI: secretary_enabled em TenantAiSettings ==========
ALTER TABLE ai_tenant_settings
  ADD COLUMN IF NOT EXISTS secretary_enabled BOOLEAN NOT NULL DEFAULT false;

-- ========== AI: Tabela TenantSecretaryProfile ==========
CREATE TABLE IF NOT EXISTS ai_tenant_secretary_profile (
  id BIGSERIAL PRIMARY KEY,
  form_data JSONB NOT NULL DEFAULT '{}',
  use_memory BOOLEAN NOT NULL DEFAULT true,
  is_active BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  tenant_id UUID NOT NULL UNIQUE REFERENCES tenancy_tenant(id) ON DELETE CASCADE
);

-- ========== AI: Índice RAG (tenant + source) ==========
CREATE INDEX IF NOT EXISTS ai_knowledge_tenant_source
  ON ai_knowledge_document (tenant_id, source);

-- ========== AI: Índice memória (tenant + conversation_id + created_at) ==========
CREATE INDEX IF NOT EXISTS ai_memory_tenant_conv_created
  ON ai_memory_item (tenant_id, conversation_id, created_at);

-- ========== AUTHN: routing_keywords em Department ==========
ALTER TABLE authn_department
  ADD COLUMN IF NOT EXISTS routing_keywords JSONB NOT NULL DEFAULT '[]';

-- ========== Registrar migrações como aplicadas (evita rodar migrate de novo) ==========
INSERT INTO django_migrations (app, name, applied)
SELECT 'ai', '0008_secretary_profile_and_indexes', NOW()
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app = 'ai' AND name = '0008_secretary_profile_and_indexes');

INSERT INTO django_migrations (app, name, applied)
SELECT 'authn', '0006_department_routing_keywords', NOW()
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app = 'authn' AND name = '0006_department_routing_keywords');

COMMIT;
