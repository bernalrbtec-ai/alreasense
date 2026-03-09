# Serviços – tabelas via SQL (sem migrations)

Novas tabelas do app **servicos** devem ser criadas com **scripts SQL** neste diretório, não com migrations Django.

Rodar os scripts manualmente no PostgreSQL (ex.: `psql -U postgres -d seu_banco -f scripts/sql/nome_do_script.sql`).

Arquivos existentes para servicos:
- `servicos_redis_cleanup_log.sql` – log de limpeza Redis
- `servicos_redis_cleanup_log_add_duration.sql` – coluna duration_seconds
- `servicos_redis_usage_sample.sql` – amostras de uso Redis (gráfico)
- `servicos_redis_usage_sample_add_breakdown.sql` – colunas keys_profile_pic, keys_webhook
- `servicos_rabbitmqoverview_sample.sql` – amostras de overview RabbitMQ (filas) para gráfico
- `servicos_postgresoverview_sample.sql` – amostras de overview PostgreSQL (conexões e tamanho) para gráfico
