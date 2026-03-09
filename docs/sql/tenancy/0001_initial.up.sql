-- Schema tenancy: convenção do projeto – alterações via scripts SQL (sem migrations .py).
-- Pré-requisito: tabela billing_plan deve existir (app billing aplicado antes).
-- Idempotente: seguro rodar mais de uma vez (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
-- Fonte: backend/apps/tenancy/migrations/tenancy_schema.sql

-- 1) Tabela (novos ambientes)
CREATE TABLE IF NOT EXISTS tenancy_tenant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(160) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    next_billing_date DATE NULL,
    ui_access BOOLEAN NOT NULL DEFAULT true,
    allow_meta_interactive_buttons BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    current_plan_id UUID NULL REFERENCES billing_plan(id) ON DELETE SET NULL
);

-- 2) Coluna em tabelas já existentes (criadas antes desta feature)
ALTER TABLE tenancy_tenant
ADD COLUMN IF NOT EXISTS allow_meta_interactive_buttons BOOLEAN NOT NULL DEFAULT true;

COMMENT ON COLUMN tenancy_tenant.allow_meta_interactive_buttons IS
  'Permite envio de mensagens com reply buttons e lista interativa (Meta/Evolution). Desative para desabilitar por tenant.';

-- 3) Índices de performance
CREATE INDEX IF NOT EXISTS idx_tenant_status ON tenancy_tenant(status);
CREATE INDEX IF NOT EXISTS idx_tenant_created_at ON tenancy_tenant(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tenant_status_created ON tenancy_tenant(status, created_at DESC);
