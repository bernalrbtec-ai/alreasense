-- Assistente: delay (segundos) antes de responder na primeira interação.
-- Aplicar no banco quando não for usar migration Django (ex.: migration 0013 removida).
-- Tabela: ai_tenant_secretary_profile

ALTER TABLE ai_tenant_secretary_profile
ADD COLUMN IF NOT EXISTS response_delay_seconds INTEGER NOT NULL DEFAULT 0;

-- Comentário opcional (PostgreSQL)
COMMENT ON COLUMN ai_tenant_secretary_profile.response_delay_seconds IS
'Segundos para aguardar antes de responder na primeira interação; 0 = imediato. Após a primeira resposta, as demais são imediatas.';
