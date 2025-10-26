-- ============================================
-- SCRIPT SQL CORRIGIDO - ÍNDICES DE PERFORMANCE
-- Criado: 26/10/2025 - VERSÃO CORRIGIDA
-- Nomes de tabelas ajustados conforme banco real
-- Remove índices já existentes
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'CRIANDO ÍNDICES DE PERFORMANCE (VERSÃO CORRIGIDA)';
    RAISE NOTICE '========================================';
    
    -- ============================================
    -- CAMPAIGNS APP
    -- ============================================
    
    RAISE NOTICE '';
    RAISE NOTICE '--- CAMPAIGNS APP ---';
    
    -- Campaign: índices principais (2 já existem, pulando)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'campaigns_campaign') THEN
        RAISE NOTICE '⚠️  idx_camp_tenant_status_created - JÁ EXISTE (pulando)';
        RAISE NOTICE '⚠️  idx_camp_tenant_active - JÁ EXISTE (pulando)';
    END IF;
    
    -- CampaignContact (nome correto: campaigns_contact)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'campaigns_contact') THEN
        RAISE NOTICE 'Criando índice: idx_cc_campaign_status';
        CREATE INDEX IF NOT EXISTS idx_cc_campaign_status 
        ON campaigns_contact(campaign_id, status);
        
        RAISE NOTICE 'Criando índice: idx_cc_campaign_failed';
        CREATE INDEX IF NOT EXISTS idx_cc_campaign_failed 
        ON campaigns_contact(campaign_id, status, retry_count) 
        WHERE status = 'failed';
        
        RAISE NOTICE 'Criando índice: idx_cc_contact_status';
        CREATE INDEX IF NOT EXISTS idx_cc_contact_status 
        ON campaigns_contact(contact_id, status);
        
        RAISE NOTICE '✅ 3 índices criados em campaigns_contact';
    ELSE
        RAISE NOTICE '⚠️  Tabela campaigns_contact não existe - pulando';
    END IF;
    
    -- CampaignLog (nome correto: campaigns_log)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'campaigns_log') THEN
        RAISE NOTICE 'Criando índice: idx_log_campaign_level_time';
        CREATE INDEX IF NOT EXISTS idx_log_campaign_level_time 
        ON campaigns_log(campaign_id, level, created_at DESC);
        
        RAISE NOTICE 'Criando índice: idx_log_tenant_level';
        CREATE INDEX IF NOT EXISTS idx_log_tenant_level 
        ON campaigns_log(tenant_id, level, created_at DESC);
        
        RAISE NOTICE '✅ 2 índices criados em campaigns_log';
    ELSE
        RAISE NOTICE '⚠️  Tabela campaigns_log não existe - pulando';
    END IF;
    
    -- CampaignNotification (tabela existe!)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'campaigns_notification') THEN
        RAISE NOTICE 'Criando índice: idx_notif_tenant_status';
        CREATE INDEX IF NOT EXISTS idx_notif_tenant_status 
        ON campaigns_notification(tenant_id, status, created_at DESC);
        
        RAISE NOTICE 'Criando índice: idx_notif_campaign_status';
        CREATE INDEX IF NOT EXISTS idx_notif_campaign_status 
        ON campaigns_notification(campaign_id, status);
        
        RAISE NOTICE '✅ 2 índices criados em campaigns_notification';
    ELSE
        RAISE NOTICE '⚠️  Tabela campaigns_notification não existe - pulando';
    END IF;
    
    -- ============================================
    -- CHAT APP
    -- ============================================
    
    RAISE NOTICE '';
    RAISE NOTICE '--- CHAT APP ---';
    
    -- Conversation
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'chat_conversation') THEN
        RAISE NOTICE 'Criando índice: idx_conv_tenant_dept_status_time';
        CREATE INDEX IF NOT EXISTS idx_conv_tenant_dept_status_time 
        ON chat_conversation(tenant_id, department_id, status, last_message_at DESC NULLS LAST);
        
        RAISE NOTICE 'Criando índice: idx_conv_tenant_status_time';
        CREATE INDEX IF NOT EXISTS idx_conv_tenant_status_time 
        ON chat_conversation(tenant_id, status, last_message_at DESC NULLS LAST) 
        WHERE status IN ('open', 'pending');
        
        RAISE NOTICE '✅ 2 índices criados em chat_conversation';
    ELSE
        RAISE NOTICE '⚠️  Tabela chat_conversation não existe - pulando';
    END IF;
    
    -- Message
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'chat_message') THEN
        RAISE NOTICE 'Criando índice: idx_msg_conv_created';
        CREATE INDEX IF NOT EXISTS idx_msg_conv_created 
        ON chat_message(conversation_id, created_at DESC);
        
        RAISE NOTICE 'Criando índice: idx_msg_conv_status_dir';
        CREATE INDEX IF NOT EXISTS idx_msg_conv_status_dir 
        ON chat_message(conversation_id, status, direction) 
        WHERE status = 'delivered' AND direction = 'incoming';
        
        RAISE NOTICE '✅ 2 índices criados em chat_message';
    ELSE
        RAISE NOTICE '⚠️  Tabela chat_message não existe - pulando';
    END IF;
    
    -- Attachment
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'chat_attachment') THEN
        RAISE NOTICE 'Criando índice: idx_attach_tenant_storage';
        CREATE INDEX IF NOT EXISTS idx_attach_tenant_storage 
        ON chat_attachment(tenant_id, storage_type, expires_at);
        
        RAISE NOTICE '✅ 1 índice criado em chat_attachment';
    ELSE
        RAISE NOTICE '⚠️  Tabela chat_attachment não existe - pulando';
    END IF;
    
    -- ============================================
    -- CONTACTS APP
    -- ============================================
    
    RAISE NOTICE '';
    RAISE NOTICE '--- CONTACTS APP ---';
    
    -- Contact
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'contacts_contact') THEN
        RAISE NOTICE 'Criando índice: idx_contact_tenant_lifecycle';
        CREATE INDEX IF NOT EXISTS idx_contact_tenant_lifecycle 
        ON contacts_contact(tenant_id, lifecycle_stage) 
        WHERE is_active = true;
        
        RAISE NOTICE 'Criando índice: idx_contact_tenant_opted';
        CREATE INDEX IF NOT EXISTS idx_contact_tenant_opted 
        ON contacts_contact(tenant_id, opted_out, is_active) 
        WHERE opted_out = false AND is_active = true;
        
        RAISE NOTICE 'Criando índice: idx_contact_tenant_state';
        CREATE INDEX IF NOT EXISTS idx_contact_tenant_state 
        ON contacts_contact(tenant_id, state) 
        WHERE state IS NOT NULL AND is_active = true;
        
        RAISE NOTICE 'Criando índice: idx_contact_tenant_phone';
        CREATE INDEX IF NOT EXISTS idx_contact_tenant_phone 
        ON contacts_contact(tenant_id, phone);
        
        RAISE NOTICE '✅ 4 índices criados em contacts_contact';
    ELSE
        RAISE NOTICE '⚠️  Tabela contacts_contact não existe - pulando';
    END IF;
    
    -- ContactList (nome correto: contacts_list)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'contacts_list') THEN
        RAISE NOTICE 'Criando índice: idx_list_tenant_active';
        CREATE INDEX IF NOT EXISTS idx_list_tenant_active 
        ON contacts_list(tenant_id, is_active);
        
        RAISE NOTICE '✅ 1 índice criado em contacts_list';
    ELSE
        RAISE NOTICE '⚠️  Tabela contacts_list não existe - pulando';
    END IF;
    
    -- Tag
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'contacts_tag') THEN
        RAISE NOTICE 'Criando índice: idx_tag_tenant';
        CREATE INDEX IF NOT EXISTS idx_tag_tenant 
        ON contacts_tag(tenant_id);
        
        RAISE NOTICE '✅ 1 índice criado em contacts_tag';
    ELSE
        RAISE NOTICE '⚠️  Tabela contacts_tag não existe - pulando';
    END IF;
    
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ CONCLUÍDO!';
    RAISE NOTICE 'Total esperado: ~17 novos índices';
    RAISE NOTICE '(2 já existiam e foram pulados)';
    RAISE NOTICE '========================================';
    
END $$;

-- ============================================
-- VALIDAÇÃO
-- ============================================

-- Ver todos os índices criados
SELECT 
    indexname,
    tablename,
    CASE 
        WHEN indexdef LIKE '%WHERE%' THEN 'Partial'
        ELSE 'Full'
    END as type,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE indexrelname IN (
    'idx_cc_campaign_status',
    'idx_cc_campaign_failed',
    'idx_cc_contact_status',
    'idx_log_campaign_level_time',
    'idx_log_tenant_level',
    'idx_notif_tenant_status',
    'idx_notif_campaign_status',
    'idx_conv_tenant_dept_status_time',
    'idx_conv_tenant_status_time',
    'idx_msg_conv_created',
    'idx_msg_conv_status_dir',
    'idx_attach_tenant_storage',
    'idx_contact_tenant_lifecycle',
    'idx_contact_tenant_opted',
    'idx_contact_tenant_state',
    'idx_contact_tenant_phone',
    'idx_list_tenant_active',
    'idx_tag_tenant'
)
ORDER BY tablename, indexname;

-- Atualizar estatísticas
ANALYZE campaigns_contact;
ANALYZE campaigns_log;
ANALYZE campaigns_notification;
ANALYZE chat_conversation;
ANALYZE chat_message;
ANALYZE chat_attachment;
ANALYZE contacts_contact;
ANALYZE contacts_list;
ANALYZE contacts_tag;

