-- Canvas: coluna media_url em chat_flow_node (tipos de nó image e file).
-- Execute se chat_flow_node foi criada pela migration 0017 (flow_schema.sql) sem media_url.
-- Idempotente: seguro rodar mais de uma vez. Pré-requisito: tabela chat_flow_node existir.

-- Adicionar coluna se não existir
ALTER TABLE chat_flow_node ADD COLUMN IF NOT EXISTS media_url VARCHAR(1024) NOT NULL DEFAULT '';

-- Garantir tipo VARCHAR(1024) (ex.: se já existia com tamanho menor)
ALTER TABLE chat_flow_node ALTER COLUMN media_url TYPE VARCHAR(1024);
