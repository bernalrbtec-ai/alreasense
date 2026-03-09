-- Adiciona colunas de breakdown (keys por categoria) em servicos_redisusagesample
-- Rodar se a migration 0002 não for aplicada (ex.: tabela criada manualmente).
-- Exemplo: psql -U postgres -d seu_banco -f scripts/sql/servicos_redis_usage_sample_add_breakdown.sql

ALTER TABLE servicos_redisusagesample
  ADD COLUMN IF NOT EXISTS keys_profile_pic INTEGER,
  ADD COLUMN IF NOT EXISTS keys_webhook INTEGER;

COMMENT ON COLUMN servicos_redisusagesample.keys_profile_pic IS 'Contagem de keys cache fotos de perfil no momento da amostra';
COMMENT ON COLUMN servicos_redisusagesample.keys_webhook IS 'Contagem de keys cache webhooks no momento da amostra';
