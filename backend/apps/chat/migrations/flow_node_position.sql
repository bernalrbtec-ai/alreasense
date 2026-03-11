-- =============================================================================
-- Posição do nó no canvas (arrastar e soltar)
-- Adiciona position_x e position_y em chat_flow_node.
-- Idempotente: pode rodar mais de uma vez (ADD COLUMN IF NOT EXISTS).
-- =============================================================================

ALTER TABLE chat_flow_node ADD COLUMN IF NOT EXISTS position_x DOUBLE PRECISION NULL;
ALTER TABLE chat_flow_node ADD COLUMN IF NOT EXISTS position_y DOUBLE PRECISION NULL;
