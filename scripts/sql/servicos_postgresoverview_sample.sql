-- Tabela de amostras de overview PostgreSQL para gráfico (conexões e tamanho do banco)
-- Rodar manualmente no PostgreSQL (ex.: psql -U postgres -d seu_banco -f scripts/sql/servicos_postgresoverview_sample.sql).
-- Após rodar: o app servicos grava amostras ao carregar o overview PostgreSQL (a cada ~10 min). Retenção 7 dias.
--
-- Exemplo: psql -U postgres -d seu_banco -f scripts/sql/servicos_postgresoverview_sample.sql

CREATE TABLE IF NOT EXISTS servicos_postgresoverview_sample (
    id BIGSERIAL PRIMARY KEY,
    sampled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    connection_count INTEGER NOT NULL,
    database_size_bytes BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_servicos_postgresoverview_sample_sampled_at
    ON servicos_postgresoverview_sample(sampled_at DESC);

COMMENT ON TABLE servicos_postgresoverview_sample IS 'Amostras de overview PostgreSQL (conexões e tamanho) para gráfico na aba Serviços';
COMMENT ON COLUMN servicos_postgresoverview_sample.connection_count IS 'Número de conexões ativas no momento da amostra';
COMMENT ON COLUMN servicos_postgresoverview_sample.database_size_bytes IS 'Tamanho do banco em bytes (pg_database_size)';
