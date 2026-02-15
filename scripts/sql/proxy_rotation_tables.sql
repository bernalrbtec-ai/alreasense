-- Proxy rotation tables (Webshare → Evolution API)
-- Rodar este SQL antes de iniciar o app proxy.
-- Depois: python manage.py migrate proxy --fake-initial

-- Tabela principal: log de cada execução de rotação
CREATE TABLE IF NOT EXISTS proxy_proxyrotationlog (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    num_proxies INTEGER NOT NULL DEFAULT 0,
    num_instances INTEGER NOT NULL DEFAULT 0,
    num_updated INTEGER NOT NULL DEFAULT 0,
    strategy VARCHAR(20) NOT NULL DEFAULT 'rotate',
    error_message TEXT,
    triggered_by VARCHAR(20) NOT NULL DEFAULT 'manual',
    created_by_id BIGINT REFERENCES authn_user(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proxy_rotation_status ON proxy_proxyrotationlog(status);
CREATE INDEX IF NOT EXISTS idx_proxy_rotation_created ON proxy_proxyrotationlog(created_at DESC);

-- Tabela de detalhes por instância
CREATE TABLE IF NOT EXISTS proxy_proxyrotationinstancelog (
    id BIGSERIAL PRIMARY KEY,
    rotation_log_id BIGINT NOT NULL REFERENCES proxy_proxyrotationlog(id) ON DELETE CASCADE,
    instance_name VARCHAR(255) NOT NULL,
    proxy_host VARCHAR(255) NOT NULL,
    proxy_port INTEGER NOT NULL,
    success BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proxy_instance_rotation ON proxy_proxyrotationinstancelog(rotation_log_id);
