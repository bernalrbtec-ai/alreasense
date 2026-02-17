-- Tabela de perfil da empresa por tenant (dados para cobrança e BIA)
-- Executar no Postgres de produção. Não usar Django migrations.
CREATE TABLE IF NOT EXISTS tenancy_company_profile (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL UNIQUE REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
  razao_social VARCHAR(200),
  cnpj VARCHAR(18),
  endereco TEXT,
  endereco_latitude DECIMAL(10, 7),
  endereco_longitude DECIMAL(10, 7),
  telefone VARCHAR(20),
  email_principal VARCHAR(254),
  ramo_atuacao VARCHAR(100),
  data_fundacao DATE,
  missao TEXT,
  sobre_empresa TEXT,
  produtos_servicos TEXT,
  logo_url VARCHAR(500),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_profile_tenant ON tenancy_company_profile(tenant_id);

-- Opcional: flag para admin testar RAG com este tenant (2 tenants autorizados)
ALTER TABLE tenancy_tenant ADD COLUMN IF NOT EXISTS rag_testing_allowed BOOLEAN DEFAULT FALSE;
