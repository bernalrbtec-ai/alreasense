-- ============================================
-- SQL para criar tabela contacts_history
-- Histórico global de interações com contatos
-- ============================================

-- Criar tabela
CREATE TABLE IF NOT EXISTS contacts_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relacionamentos principais
    contact_id UUID NOT NULL REFERENCES contacts_contact(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    
    -- Campos do evento
    event_type VARCHAR(30) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    
    -- Usuário que criou (NULL para eventos automáticos)
    created_by_id BIGINT REFERENCES authn_user(id) ON DELETE SET NULL,
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Flag de editável (apenas anotações manuais)
    is_editable BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Relacionamentos opcionais para referência
    related_conversation_id UUID REFERENCES chat_conversation(id) ON DELETE SET NULL,
    related_campaign_id UUID REFERENCES campaigns_campaign(id) ON DELETE SET NULL,
    related_message_id UUID REFERENCES chat_message(id) ON DELETE SET NULL
);

-- Índices simples (campos com db_index=True)
CREATE INDEX IF NOT EXISTS idx_contacts_history_event_type ON contacts_history(event_type);
CREATE INDEX IF NOT EXISTS idx_contacts_history_created_at ON contacts_history(created_at);

-- Índices compostos (definidos no Meta do modelo)
CREATE INDEX IF NOT EXISTS idx_contacts_history_contact_created_at 
    ON contacts_history(contact_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_contacts_history_tenant_event_created 
    ON contacts_history(tenant_id, event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_contacts_history_contact_event_type 
    ON contacts_history(contact_id, event_type);

-- Índices adicionais para performance
CREATE INDEX IF NOT EXISTS idx_contacts_history_tenant ON contacts_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_contacts_history_contact ON contacts_history(contact_id);
CREATE INDEX IF NOT EXISTS idx_contacts_history_created_by ON contacts_history(created_by_id) WHERE created_by_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_history_related_conv ON contacts_history(related_conversation_id) WHERE related_conversation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_history_related_campaign ON contacts_history(related_campaign_id) WHERE related_campaign_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_history_related_message ON contacts_history(related_message_id) WHERE related_message_id IS NOT NULL;

-- Constraint para validar event_type
ALTER TABLE contacts_history 
    ADD CONSTRAINT check_event_type 
    CHECK (event_type IN (
        'note',
        'message_sent',
        'message_received',
        'campaign_message_sent',
        'campaign_message_delivered',
        'campaign_message_read',
        'campaign_message_failed',
        'department_transfer',
        'assigned_to',
        'status_changed',
        'contact_created',
        'contact_updated'
    ));

-- Comentários nas colunas (opcional, mas útil)
COMMENT ON TABLE contacts_history IS 'Histórico global de interações com contatos - mensagens, campanhas, anotações e eventos do sistema';
COMMENT ON COLUMN contacts_history.id IS 'UUID primário do histórico';
COMMENT ON COLUMN contacts_history.contact_id IS 'FK para o contato relacionado';
COMMENT ON COLUMN contacts_history.tenant_id IS 'FK para o tenant (multi-tenancy)';
COMMENT ON COLUMN contacts_history.event_type IS 'Tipo de evento (note, message_sent, campaign_message_sent, etc.)';
COMMENT ON COLUMN contacts_history.title IS 'Título curto do evento';
COMMENT ON COLUMN contacts_history.description IS 'Descrição detalhada do evento (opcional)';
COMMENT ON COLUMN contacts_history.metadata IS 'Dados extras do evento em formato JSON';
COMMENT ON COLUMN contacts_history.created_by_id IS 'Usuário que criou o evento (NULL para eventos automáticos)';
COMMENT ON COLUMN contacts_history.created_at IS 'Timestamp de criação do evento';
COMMENT ON COLUMN contacts_history.is_editable IS 'Se o evento pode ser editado (apenas anotações manuais)';
COMMENT ON COLUMN contacts_history.related_conversation_id IS 'FK opcional para conversa relacionada';
COMMENT ON COLUMN contacts_history.related_campaign_id IS 'FK opcional para campanha relacionada';
COMMENT ON COLUMN contacts_history.related_message_id IS 'FK opcional para mensagem relacionada';

-- ✅ Tabela criada com sucesso!
-- Agora você pode usar a API /api/contacts/history/?contact_id=<uuid>

