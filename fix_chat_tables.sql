-- Script SQL para criar as tabelas do Flow Chat no Railway
-- Executar via: railway run psql < fix_chat_tables.sql

BEGIN;

-- Tabela: Conversation
CREATE TABLE IF NOT EXISTS chat_conversation (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES authn_department(id) ON DELETE CASCADE,
    contact_phone VARCHAR(20) NOT NULL,
    contact_name VARCHAR(255),
    assigned_to_id BIGINT REFERENCES authn_user(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    last_message_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_conversation_tenant ON chat_conversation(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chat_conversation_department ON chat_conversation(department_id);
CREATE INDEX IF NOT EXISTS idx_chat_conversation_phone ON chat_conversation(contact_phone);
CREATE INDEX IF NOT EXISTS idx_chat_conversation_status ON chat_conversation(status);
CREATE INDEX IF NOT EXISTS idx_chat_conversation_last_msg ON chat_conversation(last_message_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_conversation_unique ON chat_conversation(tenant_id, contact_phone);

-- Tabela: Message
CREATE TABLE IF NOT EXISTS chat_message (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES chat_conversation(id) ON DELETE CASCADE,
    sender_id BIGINT REFERENCES authn_user(id) ON DELETE SET NULL,
    content TEXT,
    direction VARCHAR(10) NOT NULL DEFAULT 'incoming',
    message_id VARCHAR(255) UNIQUE,
    evolution_status VARCHAR(50),
    error_message TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'sent',
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_message_conversation ON chat_message(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chat_message_created ON chat_message(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_message_evolution_id ON chat_message(message_id);
CREATE INDEX IF NOT EXISTS idx_chat_message_status ON chat_message(status, direction);

-- Tabela: MessageAttachment
CREATE TABLE IF NOT EXISTS chat_attachment (
    id UUID PRIMARY KEY,
    message_id UUID NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    thumbnail_path VARCHAR(500),
    storage_type VARCHAR(10) NOT NULL DEFAULT 'local',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_attachment_message ON chat_attachment(message_id);
CREATE INDEX IF NOT EXISTS idx_chat_attachment_tenant ON chat_attachment(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chat_attachment_expires ON chat_attachment(expires_at);

-- Tabela Many-to-Many: Participants
CREATE TABLE IF NOT EXISTS chat_conversation_participants (
    id BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES chat_conversation(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES authn_user(id) ON DELETE CASCADE,
    UNIQUE(conversation_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_participants_conversation ON chat_conversation_participants(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chat_participants_user ON chat_conversation_participants(user_id);

-- Marcar migration como aplicada
INSERT INTO django_migrations (app, name, applied)
VALUES ('chat', '0001_initial', NOW())
ON CONFLICT DO NOTHING;

COMMIT;

-- Verificar tabelas criadas
\dt chat_*

