-- =============================================================================
-- FLUXO CONVERSACIONAL + media_url + campos Typebot (tudo em um script para rodar direto no banco)
-- Equivalente a flow_schema.sql (0017) + flow_typebot_fields.sql + ajustes de media_url.
-- Pré-requisito: tenancy_tenant, authn_department, chat_conversation existem.
-- Idempotente: pode rodar mais de uma vez (CREATE IF NOT EXISTS, ADD COLUMN IF NOT EXISTS).
-- =============================================================================

-- 1) Fluxo
CREATE TABLE IF NOT EXISTS chat_flow (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    scope VARCHAR(20) NOT NULL DEFAULT 'inbox',
    department_id UUID NULL REFERENCES authn_department(id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_flow_tenant ON chat_flow(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chat_flow_scope_active ON chat_flow(scope, is_active);
CREATE INDEX IF NOT EXISTS idx_chat_flow_department ON chat_flow(department_id) WHERE department_id IS NOT NULL;

-- 2) Nó do fluxo (já com media_url 1024 para instalação nova)
CREATE TABLE IF NOT EXISTS chat_flow_node (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_id UUID NOT NULL REFERENCES chat_flow(id) ON DELETE CASCADE,
    node_type VARCHAR(20) NOT NULL,
    name VARCHAR(80) NOT NULL,
    "order" INTEGER NOT NULL DEFAULT 0,
    is_start BOOLEAN NOT NULL DEFAULT false,
    body_text TEXT NOT NULL DEFAULT '',
    button_text VARCHAR(20) NOT NULL DEFAULT '',
    header_text VARCHAR(60) NOT NULL DEFAULT '',
    footer_text VARCHAR(60) NOT NULL DEFAULT '',
    sections JSONB NOT NULL DEFAULT '[]',
    buttons JSONB NOT NULL DEFAULT '[]',
    media_url VARCHAR(1024) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(flow_id, name)
);

CREATE INDEX IF NOT EXISTS idx_chat_flow_node_flow ON chat_flow_node(flow_id);
CREATE INDEX IF NOT EXISTS idx_chat_flow_node_start ON chat_flow_node(flow_id, is_start) WHERE is_start = true;

-- Se a tabela já existia sem media_url (ex.: rodou 0017 antes): adicionar coluna
ALTER TABLE chat_flow_node ADD COLUMN IF NOT EXISTS media_url VARCHAR(1024) NOT NULL DEFAULT '';

-- Se media_url existia com 512: aumentar para 1024
ALTER TABLE chat_flow_node ALTER COLUMN media_url TYPE VARCHAR(1024);

-- 3) Aresta do fluxo
CREATE TABLE IF NOT EXISTS chat_flow_edge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_node_id UUID NOT NULL REFERENCES chat_flow_node(id) ON DELETE CASCADE,
    option_id VARCHAR(100) NOT NULL,
    to_node_id UUID NULL REFERENCES chat_flow_node(id) ON DELETE CASCADE,
    target_department_id UUID NULL REFERENCES authn_department(id) ON DELETE CASCADE,
    target_action VARCHAR(20) NOT NULL DEFAULT 'next',
    UNIQUE(from_node_id, option_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_flow_edge_from ON chat_flow_edge(from_node_id);

-- 4) Estado do fluxo por conversa
CREATE TABLE IF NOT EXISTS chat_conversation_flow_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL UNIQUE REFERENCES chat_conversation(id) ON DELETE CASCADE,
    flow_id UUID NOT NULL REFERENCES chat_flow(id) ON DELETE CASCADE,
    current_node_id UUID NOT NULL REFERENCES chat_flow_node(id) ON DELETE CASCADE,
    entered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_chat_conv_flow_state_conversation ON chat_conversation_flow_state(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chat_conv_flow_state_flow ON chat_conversation_flow_state(flow_id);

-- 5) Campos Typebot (idempotente: adiciona só se não existirem)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'chat_flow' AND column_name = 'typebot_public_id') THEN
    ALTER TABLE chat_flow ADD COLUMN typebot_public_id VARCHAR(100) NOT NULL DEFAULT '';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'chat_flow' AND column_name = 'typebot_base_url') THEN
    ALTER TABLE chat_flow ADD COLUMN typebot_base_url VARCHAR(200) NOT NULL DEFAULT '';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'chat_flow' AND column_name = 'typebot_prefilled_extra') THEN
    ALTER TABLE chat_flow ADD COLUMN typebot_prefilled_extra JSONB NOT NULL DEFAULT '{}';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'chat_flow' AND column_name = 'typebot_internal_id') THEN
    ALTER TABLE chat_flow ADD COLUMN typebot_internal_id VARCHAR(100) NOT NULL DEFAULT '';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'chat_flow' AND column_name = 'typebot_api_key') THEN
    ALTER TABLE chat_flow ADD COLUMN typebot_api_key VARCHAR(255) NOT NULL DEFAULT '';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'chat_conversation_flow_state' AND column_name = 'typebot_session_id') THEN
    ALTER TABLE chat_conversation_flow_state ADD COLUMN typebot_session_id VARCHAR(255) NOT NULL DEFAULT '';
  END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_chat_conv_flow_state_typebot_session ON chat_conversation_flow_state(typebot_session_id) WHERE typebot_session_id <> '';
ALTER TABLE chat_conversation_flow_state ALTER COLUMN current_node_id DROP NOT NULL;
