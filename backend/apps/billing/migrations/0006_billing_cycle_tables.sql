-- Migration: Criação das tabelas de ciclo de billing
-- Data: 2025-01-XX
-- Descrição: Cria tabelas billing_api_cycle e atualiza billing_api_contact para suportar ciclos

-- ============================================
-- 1. Tabela billing_api_cycle
-- ============================================
CREATE TABLE IF NOT EXISTS billing_api_cycle (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    external_billing_id VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(20) NOT NULL,
    contact_name VARCHAR(255) NOT NULL,
    contact_id UUID REFERENCES contacts_contact(id) ON DELETE SET NULL,
    billing_data JSONB NOT NULL DEFAULT '{}',
    due_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    notify_before_due BOOLEAN NOT NULL DEFAULT FALSE,
    notify_after_due BOOLEAN NOT NULL DEFAULT TRUE,
    total_messages INTEGER NOT NULL DEFAULT 0,
    sent_messages INTEGER NOT NULL DEFAULT 0,
    failed_messages INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    cancelled_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT unique_tenant_external_id UNIQUE (tenant_id, external_billing_id)
);

-- Índices para billing_api_cycle
CREATE INDEX IF NOT EXISTS idx_billing_cycle_tenant_status ON billing_api_cycle(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_billing_cycle_external_id ON billing_api_cycle(external_billing_id);
CREATE INDEX IF NOT EXISTS idx_billing_cycle_due_date ON billing_api_cycle(due_date);
CREATE INDEX IF NOT EXISTS idx_billing_cycle_status_created ON billing_api_cycle(status, created_at);

-- ============================================
-- 2. Atualiza billing_api_contact para suportar ciclos
-- ============================================

-- Adiciona coluna billing_cycle_id (nullable)
ALTER TABLE billing_api_contact 
ADD COLUMN IF NOT EXISTS billing_cycle_id UUID REFERENCES billing_api_cycle(id) ON DELETE CASCADE;

-- Torna campaign_contact_id nullable (mensagens de ciclo não têm CampaignContact até serem enviadas)
-- IMPORTANTE: Se já existirem dados, essa alteração é segura porque apenas permite NULL
ALTER TABLE billing_api_contact 
ALTER COLUMN campaign_contact_id DROP NOT NULL;

-- Torna billing_campaign_id nullable (mensagens agendadas não têm campanha)
-- IMPORTANTE: Se já existirem dados, essa alteração é segura porque apenas permite NULL
ALTER TABLE billing_api_contact 
ALTER COLUMN billing_campaign_id DROP NOT NULL;

-- Adiciona campos de ciclo
ALTER TABLE billing_api_contact 
ADD COLUMN IF NOT EXISTS cycle_message_type VARCHAR(30),
ADD COLUMN IF NOT EXISTS cycle_index INTEGER,
ADD COLUMN IF NOT EXISTS scheduled_date DATE,
ADD COLUMN IF NOT EXISTS billing_status VARCHAR(20) DEFAULT 'active',
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_retry_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 0;

-- Adiciona status 'cancelled' se não existir
-- (Nota: Django gerencia choices, mas garantimos que o banco aceite)

-- Índices para billing_api_contact (ciclos)
CREATE INDEX IF NOT EXISTS idx_billing_contact_cycle_status ON billing_api_contact(billing_cycle_id, status);
CREATE INDEX IF NOT EXISTS idx_billing_contact_status_scheduled_date ON billing_api_contact(status, scheduled_date);
CREATE INDEX IF NOT EXISTS idx_billing_contact_billing_status_date ON billing_api_contact(billing_status, scheduled_date);

-- ============================================
-- 3. Comentários nas tabelas
-- ============================================
COMMENT ON TABLE billing_api_cycle IS 'Ciclo completo de mensagens de cobrança (6 mensagens: 3 upcoming + 3 overdue)';
COMMENT ON COLUMN billing_api_cycle.external_billing_id IS 'ID da cobrança no sistema externo (único por tenant)';
COMMENT ON COLUMN billing_api_cycle.status IS 'Status: active, cancelled, paid, completed';
COMMENT ON COLUMN billing_api_cycle.notify_before_due IS 'Enviar avisos antes do vencimento?';
COMMENT ON COLUMN billing_api_cycle.notify_after_due IS 'Enviar avisos depois do vencimento?';

COMMENT ON COLUMN billing_api_contact.billing_cycle_id IS 'Ciclo de billing (para mensagens agendadas)';
COMMENT ON COLUMN billing_api_contact.cycle_message_type IS 'Tipo: upcoming_5d, overdue_1d, etc';
COMMENT ON COLUMN billing_api_contact.cycle_index IS 'Índice da mensagem no ciclo (1-6)';
COMMENT ON COLUMN billing_api_contact.scheduled_date IS 'Data agendada (já ajustada para dia útil)';
COMMENT ON COLUMN billing_api_contact.billing_status IS 'Status da cobrança: active, cancelled, paid';
COMMENT ON COLUMN billing_api_contact.version IS 'Versão para lock otimista';

