# Serviços: estatísticas, monitoramento e alertas para superadmin

## Objetivo

- Guardar amostras de uso (RabbitMQ e PostgreSQL) para estatísticas e picos.
- Expor pico de uso, espaço e memória nos overviews (Redis já tem histórico).
- Alertas de uso (ex.: memória Redis alta, muitas conexões Postgres, fila RabbitMQ cheia) visíveis ao superadmin na tela Serviços.

---

## 1. Dados a guardar

| Serviço    | Já existe | Novo | Conteúdo |
|-----------|-----------|------|----------|
| Redis     | Sim       | Não  | RedisUsageSample: used_memory, aof, keys_profile_pic, keys_webhook. Retenção 7 dias. |
| RabbitMQ  | Não       | Sim  | Uma amostra por momento: lista de filas com messages_ready e consumers (JSON ou tabela normalizada). |
| PostgreSQL| Não       | Sim  | Uma amostra por momento: connection_count, database_size_bytes. |

**Quando gravar:** ao carregar o overview do respectivo serviço (GET overview), com throttle de 10 min (igual Redis), para não encher o banco.

**Retenção:** 7 dias (apagar amostras mais antigas ao gravar).

---

## 2. Tabelas (apenas scripts SQL, sem migrations)

- **servicos_rabbitmqoverview_sample**  
  - `id` (BIGSERIAL), `sampled_at` (TIMESTAMPTZ), `payload` (JSONB).  
  - `payload`: lista de `{ "name", "messages_ready", "consumers" }` por fila.  
  - Permite consultar pico de mensagens por fila e no total.

- **servicos_postgresoverview_sample**  
  - `id` (BIGSERIAL), `sampled_at` (TIMESTAMPTZ), `connection_count` (INT), `database_size_bytes` (BIGINT).  
  - Permite gráfico de conexões e tamanho ao longo do tempo e pico.

Scripts em `scripts/sql/` (ex.: `servicos_rabbitmqoverview_sample.sql`, `servicos_postgresoverview_sample.sql`), conforme padrão do README_servicos.

---

## 3. Backend

- **Modelos:** opcionalmente modelos Django com `managed = False` apontando para essas tabelas (leitura/escrita via ORM; tabela criada só pelo SQL).
- **Gravação:** em `rabbitmq_overview` e `postgres_overview`, após obter os dados:
  - Se última amostra da tabela for mais antiga que 10 min, inserir nova amostra.
  - Apagar amostras com `sampled_at` &lt; now - 7 dias.
- **Resposta dos overviews:** além do estado atual, retornar (opcional na v1):
  - **Redis:** já retorna `usage_history`; pode adicionar `peak_24h_memory_bytes` (max das amostras nas últimas 24h).
  - **RabbitMQ:** adicionar `usage_history` (últimas N amostras) e `peak_24h_messages` (max de soma de messages_ready por sample).
  - **PostgreSQL:** adicionar `usage_history` e `peak_24h_connections`, `peak_24h_size_bytes`.
- **Alertas:** novo endpoint GET `servicos/alerts/` (ou incluir em cada overview) que:
  - Lê limites por variável de ambiente (ou tabela de configuração futura), ex.:  
    `REDIS_MEMORY_ALERT_MB`, `POSTGRES_CONNECTIONS_ALERT`, `RABBITMQ_QUEUE_MESSAGES_ALERT`.
  - Compara valor atual (e opcionalmente último pico) com o limite.
  - Retorna lista de alertas: `{ "level": "warning"|"critical", "service": "redis"|"rabbitmq"|"postgres", "message": "...", "current": number, "threshold": number }`.
  - Acesso: só superadmin (no backend: `is_superuser` ou `is_staff`; frontend usa a mesma regra para exibir a página Serviços).

---

## 4. Frontend (Serviços)

- **Estatísticas / picos:** nos cards RabbitMQ e PostgreSQL, mostrar (quando houver dados):
  - Texto do tipo: “Pico 24h: X conexões” ou “Pico 24h: Y mensagens (filas)”.
  - Opcional: mini gráfico (últimas 24h) usando o `usage_history` (como no Redis).
- **Alertas:**
  - Card ou faixa no topo da página Serviços (visível só para superadmin): “Alertas de uso”.
  - Se GET `servicos/alerts/` (ou equivalente) tiver itens, listar com ícone de aviso e mensagem (ex.: “Redis: memória acima de 400 MB”).
  - Pode ser um único componente que chama o endpoint de alertas ao montar a página.

---

## 5. Ordem sugerida

1. Scripts SQL para as duas novas tabelas + README_servicos atualizado.
2. Backend: modelos (managed=False), gravar amostra em rabbitmq/postgres overview, limpar &gt; 7 dias, retornar `usage_history` e picos (peak_24h) nos overviews.
3. Backend: endpoint de alertas (limites via env) e inclusão dos alertas na resposta ou em GET separado.
4. Frontend: exibir picos nos cards RabbitMQ/PostgreSQL; exibir bloco de alertas no topo da página Serviços.

---

## 6. Limites (env) – sugestão

- `REDIS_MEMORY_ALERT_MB`: ex.: 400 (aviso se used_memory &gt; 400 MB).
- `POSTGRES_CONNECTIONS_ALERT`: ex.: 80 (aviso se connection_count &gt; 80).
- `RABBITMQ_QUEUE_MESSAGES_ALERT`: ex.: 1000 (aviso se alguma fila tiver messages_ready &gt; 1000).

Valores padrão podem ser fixos no código se as env não estiverem definidas.
