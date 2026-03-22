-- proxy.0002_proxyrotationschedule — PostgreSQL (manual)
-- Equivale à migration Django apps/proxy/migrations/0002_proxyrotationschedule.py
--
-- Pré-requisitos:
--   - Tabela authn_user já existe (AUTH_USER_MODEL = authn.User).
--   - Migration proxy.0001_initial já aplicada (tabelas proxy_proxyrotationlog, etc.).
--
-- Depois de executar este script, marque a migration como aplicada (um dos dois):
--
-- SQL:
--   INSERT INTO django_migrations (app, name, applied)
--   SELECT 'proxy', '0002_proxyrotationschedule', NOW() AT TIME ZONE 'UTC'
--   WHERE NOT EXISTS (
--     SELECT 1 FROM django_migrations WHERE app = 'proxy' AND name = '0002_proxyrotationschedule'
--   );
--
-- Ou no servidor:
--   python manage.py migrate proxy --fake 0002_proxyrotationschedule

BEGIN;

CREATE TABLE IF NOT EXISTS proxy_proxyrotationschedule (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    interval_minutes INTEGER NOT NULL DEFAULT 1440,
    strategy VARCHAR(20) NOT NULL DEFAULT 'rotate',
    last_run_at TIMESTAMPTZ NULL,
    next_run_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    created_by_id BIGINT NULL,
    CONSTRAINT proxy_proxyrotationschedule_created_by_id_fk
        FOREIGN KEY (created_by_id)
        REFERENCES authn_user (id)
        ON DELETE SET NULL
        DEFERRABLE INITIALLY DEFERRED
);

-- db_index em is_active
CREATE INDEX IF NOT EXISTS proxy_proxyrotationschedule_is_active_b7430a56
    ON proxy_proxyrotationschedule (is_active);

-- db_index em next_run_at
CREATE INDEX IF NOT EXISTS proxy_proxyrotationschedule_next_run_at_7c8e1b2a
    ON proxy_proxyrotationschedule (next_run_at);

-- Índice composto (migration AddIndex)
CREATE INDEX IF NOT EXISTS proxy_proxyrotationschedule_is_active_next_run_idx
    ON proxy_proxyrotationschedule (is_active, next_run_at);

COMMIT;
