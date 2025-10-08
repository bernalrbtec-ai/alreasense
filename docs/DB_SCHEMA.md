# 🗄️ EvoSense - Database Schema

## Visão Geral

O banco de dados do EvoSense utiliza PostgreSQL 15+ com a extensão pgvector para busca semântica. A arquitetura é multi-tenant com isolamento por linha (`tenant_id`).

## Extensões

```sql
-- Extensão para busca vetorial
CREATE EXTENSION IF NOT EXISTS vector;
```

## Tabelas Principais

### 1. tenancy_tenant
Armazena informações dos tenants (empresas/clientes).

```sql
CREATE TABLE tenancy_tenant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(160) NOT NULL,
    plan VARCHAR(32) DEFAULT 'starter' CHECK (plan IN ('starter', 'pro', 'scale', 'enterprise')),
    next_billing_date DATE,
    status VARCHAR(16) DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'trial')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Índices:**
```sql
CREATE INDEX idx_tenant_plan ON tenancy_tenant(plan);
CREATE INDEX idx_tenant_status ON tenancy_tenant(status);
CREATE INDEX idx_tenant_billing ON tenancy_tenant(next_billing_date);
```

### 2. authn_user
Usuários do sistema com isolamento por tenant.

```sql
CREATE TABLE authn_user (
    id BIGSERIAL PRIMARY KEY,
    password VARCHAR(128) NOT NULL,
    last_login TIMESTAMP WITH TIME ZONE,
    is_superuser BOOLEAN DEFAULT FALSE,
    username VARCHAR(150) UNIQUE NOT NULL,
    first_name VARCHAR(150),
    last_name VARCHAR(150),
    email VARCHAR(254),
    is_staff BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    date_joined TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    role VARCHAR(16) DEFAULT 'operator' CHECK (role IN ('admin', 'operator'))
);
```

**Índices:**
```sql
CREATE INDEX idx_user_tenant ON authn_user(tenant_id);
CREATE INDEX idx_user_username ON authn_user(username);
CREATE INDEX idx_user_email ON authn_user(email);
```

### 3. connections_evolutionconnection
Conexões com a Evolution API.

```sql
CREATE TABLE connections_evolutionconnection (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL,
    evo_ws_url TEXT NOT NULL,
    evo_token VARCHAR(255) NOT NULL, -- Criptografado
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);
```

**Índices:**
```sql
CREATE INDEX idx_connection_tenant ON connections_evolutionconnection(tenant_id);
CREATE INDEX idx_connection_active ON connections_evolutionconnection(is_active);
```

### 4. messages_message
Mensagens do WhatsApp com análise de IA e embeddings.

```sql
CREATE TABLE messages_message (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    connection_id BIGINT REFERENCES connections_evolutionconnection(id) ON DELETE SET NULL,
    chat_id VARCHAR(128) NOT NULL,
    sender VARCHAR(64) NOT NULL, -- Hash do número
    text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Resultados da análise de IA
    sentiment FLOAT CHECK (sentiment >= -1 AND sentiment <= 1),
    emotion VARCHAR(40),
    satisfaction INTEGER CHECK (satisfaction >= 0 AND satisfaction <= 100),
    tone VARCHAR(40),
    summary VARCHAR(200),
    
    -- Embedding vetorial (pgvector)
    embedding vector(768)
);
```

**Índices:**
```sql
-- Índices básicos
CREATE INDEX idx_message_tenant ON messages_message(tenant_id);
CREATE INDEX idx_message_created_at ON messages_message(created_at);
CREATE INDEX idx_message_chat_id ON messages_message(chat_id);
CREATE INDEX idx_message_sender ON messages_message(sender);

-- Índice GIN para busca full-text
CREATE INDEX idx_message_text_gin ON messages_message USING gin(to_tsvector('portuguese', text));

-- Índice IVFFLAT para busca vetorial
CREATE INDEX idx_message_embedding ON messages_message 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Índices compostos para consultas comuns
CREATE INDEX idx_message_tenant_created ON messages_message(tenant_id, created_at);
CREATE INDEX idx_message_tenant_sentiment ON messages_message(tenant_id, sentiment);
```

### 5. experiments_prompttemplate
Templates de prompt para experimentos de IA.

```sql
CREATE TABLE experiments_prompttemplate (
    id BIGSERIAL PRIMARY KEY,
    version VARCHAR(64) UNIQUE NOT NULL,
    body TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100)
);
```

**Índices:**
```sql
CREATE INDEX idx_prompt_version ON experiments_prompttemplate(version);
CREATE INDEX idx_prompt_active ON experiments_prompttemplate(is_active);
```

### 6. experiments_inference
Resultados de inferências de IA para experimentos.

```sql
CREATE TABLE experiments_inference (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    message_id BIGINT NOT NULL REFERENCES messages_message(id) ON DELETE CASCADE,
    model_name VARCHAR(64) NOT NULL,
    prompt_version VARCHAR(64) NOT NULL,
    template_hash VARCHAR(64) NOT NULL,
    latency_ms INTEGER NOT NULL,
    sentiment FLOAT NOT NULL,
    emotion VARCHAR(40) NOT NULL,
    satisfaction INTEGER NOT NULL,
    is_shadow BOOLEAN DEFAULT FALSE,
    run_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Índices:**
```sql
CREATE INDEX idx_inference_tenant ON experiments_inference(tenant_id);
CREATE INDEX idx_inference_message ON experiments_inference(message_id);
CREATE INDEX idx_inference_run_id ON experiments_inference(run_id);
CREATE INDEX idx_inference_created_at ON experiments_inference(created_at);
CREATE INDEX idx_inference_shadow ON experiments_inference(is_shadow);
CREATE INDEX idx_inference_prompt ON experiments_inference(prompt_version);
```

### 7. experiments_experimentrun
Controle de execução de experimentos.

```sql
CREATE TABLE experiments_experimentrun (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    run_id VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    prompt_version VARCHAR(64) NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE,
    status VARCHAR(16) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    total_messages INTEGER DEFAULT 0,
    processed_messages INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Índices:**
```sql
CREATE INDEX idx_experiment_tenant ON experiments_experimentrun(tenant_id);
CREATE INDEX idx_experiment_run_id ON experiments_experimentrun(run_id);
CREATE INDEX idx_experiment_status ON experiments_experimentrun(status);
CREATE INDEX idx_experiment_created ON experiments_experimentrun(created_at);
```

### 8. billing_paymentaccount
Contas de pagamento Stripe.

```sql
CREATE TABLE billing_paymentaccount (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID UNIQUE NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    stripe_customer_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_subscription_id VARCHAR(255),
    status VARCHAR(16) DEFAULT 'pending' CHECK (status IN ('active', 'expired', 'pending', 'cancelled')),
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Índices:**
```sql
CREATE INDEX idx_payment_tenant ON billing_paymentaccount(tenant_id);
CREATE INDEX idx_payment_stripe_customer ON billing_paymentaccount(stripe_customer_id);
CREATE INDEX idx_payment_status ON billing_paymentaccount(status);
```

### 9. billing_billingevent
Eventos de billing do Stripe.

```sql
CREATE TABLE billing_billingevent (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    stripe_event_id VARCHAR(255) UNIQUE NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Índices:**
```sql
CREATE INDEX idx_billing_event_tenant ON billing_billingevent(tenant_id);
CREATE INDEX idx_billing_event_type ON billing_billingevent(event_type);
CREATE INDEX idx_billing_event_stripe ON billing_billingevent(stripe_event_id);
CREATE INDEX idx_billing_event_processed ON billing_billingevent(processed);
CREATE INDEX idx_billing_event_created ON billing_billingevent(created_at);
```

## Views e Funções

### 1. View de Métricas do Tenant
```sql
CREATE VIEW tenant_metrics AS
SELECT 
    t.id as tenant_id,
    t.name as tenant_name,
    t.plan,
    COUNT(m.id) as total_messages,
    AVG(m.sentiment) as avg_sentiment,
    AVG(m.satisfaction) as avg_satisfaction,
    COUNT(CASE WHEN m.sentiment > 0.1 THEN 1 END) * 100.0 / COUNT(m.id) as positive_pct,
    COUNT(CASE WHEN m.created_at >= CURRENT_DATE THEN 1 END) as messages_today,
    COUNT(DISTINCT c.id) as active_connections,
    AVG(i.latency_ms) as avg_latency_ms
FROM tenancy_tenant t
LEFT JOIN messages_message m ON t.id = m.tenant_id
LEFT JOIN connections_evolutionconnection c ON t.id = c.tenant_id AND c.is_active = true
LEFT JOIN experiments_inference i ON t.id = i.tenant_id
GROUP BY t.id, t.name, t.plan;
```

### 2. Função de Busca Semântica
```sql
CREATE OR REPLACE FUNCTION semantic_search(
    p_tenant_id UUID,
    p_query_embedding vector(768),
    p_limit INTEGER DEFAULT 20,
    p_similarity_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    message_id BIGINT,
    text TEXT,
    sentiment FLOAT,
    satisfaction INTEGER,
    similarity_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        m.text,
        m.sentiment,
        m.satisfaction,
        1 - (m.embedding <=> p_query_embedding) as similarity_score,
        m.created_at
    FROM messages_message m
    WHERE m.tenant_id = p_tenant_id
        AND m.embedding IS NOT NULL
        AND (1 - (m.embedding <=> p_query_embedding)) >= p_similarity_threshold
    ORDER BY m.embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;
```

## Políticas de Retenção

### Limpeza Automática por Plano
```sql
-- Função para limpeza baseada no plano
CREATE OR REPLACE FUNCTION cleanup_old_messages()
RETURNS INTEGER AS $$
DECLARE
    tenant_record RECORD;
    cutoff_date DATE;
    deleted_count INTEGER := 0;
BEGIN
    FOR tenant_record IN 
        SELECT id, plan FROM tenancy_tenant WHERE status = 'active'
    LOOP
        -- Determinar data de corte baseada no plano
        CASE tenant_record.plan
            WHEN 'starter' THEN cutoff_date := CURRENT_DATE - INTERVAL '30 days';
            WHEN 'pro' THEN cutoff_date := CURRENT_DATE - INTERVAL '180 days';
            WHEN 'scale' THEN cutoff_date := CURRENT_DATE - INTERVAL '365 days';
            WHEN 'enterprise' THEN cutoff_date := CURRENT_DATE - INTERVAL '730 days';
            ELSE cutoff_date := CURRENT_DATE - INTERVAL '30 days';
        END CASE;
        
        -- Deletar mensagens antigas
        DELETE FROM messages_message 
        WHERE tenant_id = tenant_record.id 
            AND created_at < cutoff_date;
        
        GET DIAGNOSTICS deleted_count = deleted_count + ROW_COUNT;
    END LOOP;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
```

## Monitoramento

### Queries de Monitoramento
```sql
-- Estatísticas de uso por tenant
SELECT 
    t.name,
    t.plan,
    COUNT(m.id) as message_count,
    COUNT(CASE WHEN m.embedding IS NOT NULL THEN 1 END) as embedded_count,
    pg_size_pretty(pg_total_relation_size('messages_message')) as table_size
FROM tenancy_tenant t
LEFT JOIN messages_message m ON t.id = m.tenant_id
GROUP BY t.id, t.name, t.plan
ORDER BY message_count DESC;

-- Performance do índice vetorial
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes 
WHERE indexname = 'idx_message_embedding';

-- Estatísticas de embeddings
SELECT 
    COUNT(*) as total_messages,
    COUNT(embedding) as messages_with_embeddings,
    ROUND(COUNT(embedding) * 100.0 / COUNT(*), 2) as embedding_coverage
FROM messages_message;
```

## Backup e Manutenção

### Backup Strategy
```bash
# Backup completo
pg_dump -h localhost -U postgres -d evosense > evosense_backup.sql

# Backup apenas dados (sem schema)
pg_dump -h localhost -U postgres -d evosense --data-only > evosense_data.sql

# Backup específico por tenant
pg_dump -h localhost -U postgres -d evosense \
  --table=messages_message \
  --where="tenant_id='<tenant-uuid>'" \
  > tenant_messages.sql
```

### Manutenção do pgvector
```sql
-- Reindexar índice vetorial (quando necessário)
REINDEX INDEX idx_message_embedding;

-- Atualizar estatísticas
ANALYZE messages_message;

-- Verificar saúde do índice
SELECT * FROM pg_stat_user_indexes WHERE indexname = 'idx_message_embedding';
```
