-- =============================================================================
-- Nó tipo timer (delay): espera em segundos antes da próxima etapa
-- Adiciona delay_seconds em chat_flow_node.
-- Idempotente: pode rodar mais de uma vez (ADD COLUMN IF NOT EXISTS).
-- =============================================================================

ALTER TABLE chat_flow_node ADD COLUMN IF NOT EXISTS delay_seconds INTEGER NULL;

COMMENT ON COLUMN chat_flow_node.delay_seconds IS 'Para tipo timer (delay): quantos segundos esperar antes da próxima etapa (1 a 86400).';
