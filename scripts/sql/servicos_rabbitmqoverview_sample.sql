-- Tabela de amostras de overview RabbitMQ para gráfico (filas: mensagens e consumidores)
-- Rodar manualmente no PostgreSQL (ex.: psql -U postgres -d seu_banco -f scripts/sql/servicos_rabbitmqoverview_sample.sql).
-- Após rodar: o app servicos grava amostras ao carregar o overview RabbitMQ (a cada ~10 min). Retenção 7 dias.
--
-- Exemplo: psql -U postgres -d seu_banco -f scripts/sql/servicos_rabbitmqoverview_sample.sql

CREATE TABLE IF NOT EXISTS servicos_rabbitmqoverview_sample (
    id BIGSERIAL PRIMARY KEY,
    sampled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_servicos_rabbitmqoverview_sample_sampled_at
    ON servicos_rabbitmqoverview_sample(sampled_at DESC);

COMMENT ON TABLE servicos_rabbitmqoverview_sample IS 'Amostras de overview RabbitMQ (filas: name, messages_ready, consumers) para gráfico na aba Serviços';
COMMENT ON COLUMN servicos_rabbitmqoverview_sample.payload IS 'Array de objetos: { "name": "fila", "messages_ready": N, "consumers": M }';
