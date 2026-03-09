-- Schema fluxo conversacional (lista/botões por Inbox ou departamento).
-- ATENÇÃO: Este script é diferente do tenancy_schema.sql (que altera tenancy_tenant).
-- Aqui criamos: chat_flow, chat_flow_node, chat_flow_edge, chat_conversation_flow_state.
-- Convenção: alterações via scripts SQL. Pré-requisito: tenancy_tenant, authn_department, chat_conversation.
-- Idempotente: CREATE TABLE IF NOT EXISTS.
-- Fonte: backend/apps/chat/migrations/flow_schema.sql

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

-- 2) Nó do fluxo
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(flow_id, name)
);

CREATE INDEX IF NOT EXISTS idx_chat_flow_node_flow ON chat_flow_node(flow_id);
CREATE INDEX IF NOT EXISTS idx_chat_flow_node_start ON chat_flow_node(flow_id, is_start) WHERE is_start = true;

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
