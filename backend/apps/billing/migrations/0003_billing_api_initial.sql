-- Migration: billing_api_initial
-- Description: Cria todas as tabelas do sistema de billing API
-- Created: 2025-12

-- ============================================
-- 1. BillingConfig
-- ============================================
CREATE TABLE IF NOT EXISTS billing_api_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL UNIQUE REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    messages_per_minute INTEGER NOT NULL DEFAULT 20 CHECK (messages_per_minute >= 1 AND messages_per_minute <= 60),
    max_messages_per_day INTEGER CHECK (max_messages_per_day >= 1),
    use_business_hours BOOLEAN NOT NULL DEFAULT TRUE,
    max_retries INTEGER NOT NULL DEFAULT 3 CHECK (max_retries >= 0 AND max_retries <= 10),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS billing_api_config_tenant_idx ON billing_api_config(tenant_id);

COMMENT ON TABLE billing_api_config IS 'Configurações do sistema de cobrança por tenant';
COMMENT ON COLUMN billing_api_config.tenant_id IS 'Tenant (OneToOne)';
COMMENT ON COLUMN billing_api_config.messages_per_minute IS 'Máximo de mensagens por minuto (1-60)';
COMMENT ON COLUMN billing_api_config.max_messages_per_day IS 'Máximo de mensagens por dia (null = ilimitado)';
COMMENT ON COLUMN billing_api_config.use_business_hours IS 'Respeitar horário comercial para envios';
COMMENT ON COLUMN billing_api_config.max_retries IS 'Máximo de tentativas em caso de falha (0-10)';

-- ============================================
-- 2. BillingAPIKey
-- ============================================
CREATE TABLE IF NOT EXISTS billing_api_key (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    key VARCHAR(64) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    rate_limit_per_hour INTEGER,
    allowed_ips JSONB NOT NULL DEFAULT '[]',
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS billing_api_key_tenant_is_active_idx ON billing_api_key(tenant_id, is_active);
CREATE INDEX IF NOT EXISTS billing_api_key_key_idx ON billing_api_key(key);
CREATE INDEX IF NOT EXISTS billing_api_key_expires_at_idx ON billing_api_key(expires_at);

COMMENT ON TABLE billing_api_key IS 'API Keys para acesso externo ao sistema de cobrança';
COMMENT ON COLUMN billing_api_key.tenant_id IS 'Tenant';
COMMENT ON COLUMN billing_api_key.name IS 'Nome descritivo da API Key';
COMMENT ON COLUMN billing_api_key.key IS 'API Key (gerada automaticamente)';
COMMENT ON COLUMN billing_api_key.rate_limit_per_hour IS 'Máximo de requisições por hora (null = ilimitado)';
COMMENT ON COLUMN billing_api_key.allowed_ips IS 'Lista de IPs permitidos (JSON array)';
COMMENT ON COLUMN billing_api_key.expires_at IS 'Data de expiração (null = nunca expira)';

-- ============================================
-- 3. BillingTemplate
-- ============================================
CREATE TABLE IF NOT EXISTS billing_api_template (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    template_type VARCHAR(20) NOT NULL CHECK (template_type IN ('overdue', 'upcoming', 'notification')),
    description TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, name, template_type)
);

CREATE INDEX IF NOT EXISTS billing_api_template_tenant_type_active_idx ON billing_api_template(tenant_id, template_type, is_active);

COMMENT ON TABLE billing_api_template IS 'Templates de mensagens de cobrança';
COMMENT ON COLUMN billing_api_template.tenant_id IS 'Tenant';
COMMENT ON COLUMN billing_api_template.name IS 'Nome do template';
COMMENT ON COLUMN billing_api_template.template_type IS 'Tipo: overdue, upcoming, notification';

-- ============================================
-- 4. BillingTemplateVariation
-- ============================================
CREATE TABLE IF NOT EXISTS billing_api_template_variation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES billing_api_template(id) ON DELETE CASCADE,
    "order" INTEGER NOT NULL CHECK ("order" >= 1 AND "order" <= 5),
    template_text TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(template_id, "order")
);

CREATE INDEX IF NOT EXISTS billing_api_template_variation_template_active_order_idx ON billing_api_template_variation(template_id, is_active, "order");

COMMENT ON TABLE billing_api_template_variation IS 'Variações de template (anti-bloqueio WhatsApp)';
COMMENT ON COLUMN billing_api_template_variation.template_id IS 'Template pai';
COMMENT ON COLUMN billing_api_template_variation."order" IS 'Ordem da variação (1-5)';
COMMENT ON COLUMN billing_api_template_variation.template_text IS 'Texto do template com variáveis';

-- ============================================
-- 5. BillingCampaign
-- ============================================
CREATE TABLE IF NOT EXISTS billing_api_campaign (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    campaign_id UUID NOT NULL UNIQUE REFERENCES campaigns_campaign(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES billing_api_template(id) ON DELETE RESTRICT,
    external_id VARCHAR(255),
    billing_type VARCHAR(20) NOT NULL CHECK (billing_type IN ('overdue', 'upcoming', 'notification')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS billing_api_campaign_tenant_type_idx ON billing_api_campaign(tenant_id, billing_type);
CREATE INDEX IF NOT EXISTS billing_api_campaign_external_id_idx ON billing_api_campaign(external_id);
CREATE INDEX IF NOT EXISTS billing_api_campaign_created_at_idx ON billing_api_campaign(created_at);

COMMENT ON TABLE billing_api_campaign IS 'Campanha de cobrança (reutiliza Campaign)';
COMMENT ON COLUMN billing_api_campaign.tenant_id IS 'Tenant';
COMMENT ON COLUMN billing_api_campaign.campaign_id IS 'Campanha (OneToOne - reutiliza)';
COMMENT ON COLUMN billing_api_campaign.template_id IS 'Template usado';
COMMENT ON COLUMN billing_api_campaign.external_id IS 'ID externo fornecido pelo cliente';
COMMENT ON COLUMN billing_api_campaign.billing_type IS 'Tipo: overdue, upcoming, notification';

-- ============================================
-- 6. BillingQueue
-- ============================================
CREATE TABLE IF NOT EXISTS billing_api_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    billing_campaign_id UUID NOT NULL UNIQUE REFERENCES billing_api_campaign(id) ON DELETE CASCADE,
    status VARCHAR(30) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'paused', 'paused_business_hours', 'paused_instance_down', 'completed', 'cancelled')),
    total_contacts INTEGER NOT NULL DEFAULT 0,
    processed_contacts INTEGER NOT NULL DEFAULT 0,
    sent_contacts INTEGER NOT NULL DEFAULT 0,
    failed_contacts INTEGER NOT NULL DEFAULT 0,
    processing_by VARCHAR(255) NOT NULL DEFAULT '',
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    scheduled_for TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS billing_api_queue_status_scheduled_idx ON billing_api_queue(status, scheduled_for);
CREATE INDEX IF NOT EXISTS billing_api_queue_processing_status_idx ON billing_api_queue(processing_by, status);
CREATE INDEX IF NOT EXISTS billing_api_queue_created_at_idx ON billing_api_queue(created_at);

COMMENT ON TABLE billing_api_queue IS 'Fila de processamento de cobranças';
COMMENT ON COLUMN billing_api_queue.billing_campaign_id IS 'Campanha de billing (OneToOne)';
COMMENT ON COLUMN billing_api_queue.status IS 'Status da fila';
COMMENT ON COLUMN billing_api_queue.total_contacts IS 'Total de contatos na campanha';
COMMENT ON COLUMN billing_api_queue.processed_contacts IS 'Contatos processados';
COMMENT ON COLUMN billing_api_queue.sent_contacts IS 'Contatos com mensagem enviada';
COMMENT ON COLUMN billing_api_queue.failed_contacts IS 'Contatos com falha';
COMMENT ON COLUMN billing_api_queue.processing_by IS 'ID do worker que está processando';
COMMENT ON COLUMN billing_api_queue.last_heartbeat IS 'Último heartbeat do worker';
COMMENT ON COLUMN billing_api_queue.scheduled_for IS 'Próxima execução agendada (para retomadas)';

-- ============================================
-- 7. BillingContact
-- ============================================
CREATE TABLE IF NOT EXISTS billing_api_contact (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    billing_campaign_id UUID NOT NULL REFERENCES billing_api_campaign(id) ON DELETE CASCADE,
    campaign_contact_id UUID NOT NULL UNIQUE REFERENCES campaigns_contact(id) ON DELETE CASCADE,
    template_variation_id UUID REFERENCES billing_api_template_variation(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sending', 'sent', 'delivered', 'read', 'failed', 'pending_retry')),
    rendered_message TEXT NOT NULL DEFAULT '',
    billing_data JSONB NOT NULL DEFAULT '{}',
    scheduled_at TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS billing_api_contact_campaign_status_idx ON billing_api_contact(billing_campaign_id, status);
CREATE INDEX IF NOT EXISTS billing_api_contact_status_scheduled_idx ON billing_api_contact(status, scheduled_at);
CREATE INDEX IF NOT EXISTS billing_api_contact_created_at_idx ON billing_api_contact(created_at);

COMMENT ON TABLE billing_api_contact IS 'Contato de cobrança (reutiliza CampaignContact)';
COMMENT ON COLUMN billing_api_contact.billing_campaign_id IS 'Campanha de billing';
COMMENT ON COLUMN billing_api_contact.campaign_contact_id IS 'Contato da campanha (OneToOne - reutiliza)';
COMMENT ON COLUMN billing_api_contact.template_variation_id IS 'Variação de template usada';
COMMENT ON COLUMN billing_api_contact.status IS 'Status do envio';
COMMENT ON COLUMN billing_api_contact.rendered_message IS 'Mensagem final renderizada (com variáveis substituídas)';
COMMENT ON COLUMN billing_api_contact.billing_data IS 'Dados da cobrança (valor, vencimento, link, pix, etc.) em JSON';



