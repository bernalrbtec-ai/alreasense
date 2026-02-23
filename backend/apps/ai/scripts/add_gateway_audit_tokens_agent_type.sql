-- BIA: input_tokens, output_tokens, agent_type em ai_gateway_audit (bia.doc)
-- Rodar manualmente antes do deploy. Migration 0013 foi removida para não rodar no deploy.

ALTER TABLE ai_gateway_audit ADD COLUMN IF NOT EXISTS input_tokens INTEGER NULL;
ALTER TABLE ai_gateway_audit ADD COLUMN IF NOT EXISTS output_tokens INTEGER NULL;
ALTER TABLE ai_gateway_audit ADD COLUMN IF NOT EXISTS agent_type VARCHAR(50) NULL;

CREATE INDEX IF NOT EXISTS ai_gateway_tenant_agent_created_idx
ON ai_gateway_audit(tenant_id, agent_type, created_at);
