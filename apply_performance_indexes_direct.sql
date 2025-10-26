-- ============================================
-- SCRIPT SQL DIRETO - ÍNDICES DE PERFORMANCE
-- Criado: 26/10/2025
-- Propósito: Adicionar índices compostos otimizados
-- Seguro: Idempotente, verifica existência de tabelas
-- ============================================

-- ============================================
-- PARTE 1: INVESTIGAÇÃO (Execute primeiro)
-- ============================================

-- 1. Ver todas as tabelas disponíveis
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- 2. Ver índices existentes em campanhas
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename LIKE 'campaigns_%'
ORDER BY tablename, indexname;

-- 3. Ver índices existentes em chat
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename LIKE 'chat_%'
ORDER BY tablename, indexname;

-- 4. Ver índices existentes em contacts
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename LIKE 'contacts_%'
ORDER BY tablename, indexname;

-- 5. Ver tamanho das tabelas e índices
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables
WHERE schemaname = 'public'
  AND (tablename LIKE 'campaigns_%' 
    OR tablename LIKE 'chat_%' 
    OR tablename LIKE 'contacts_%')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;


-- ============================================
-- PARTE 2: CRIAÇÃO DE ÍNDICES (Execute depois)
-- ============================================

-- Este bloco é completamente seguro:
-- - Só cria índice se tabela existir
-- - Usa IF NOT EXISTS
-- - Pode rodar múltiplas vezes
-- - Não quebra nada

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'INICIANDO CRIAÇÃO DE ÍNDICES DE PERFORMANCE';
    RAISE NOTICE '========================================';
    
    -- ============================================
    -- CAMPAIGNS APP
    -- ============================================
    
    RAISE NOTICE '';
    RAISE NOTICE '--- CAMPAIGNS APP ---';
    
    -- Campaign: tenant + status + ordering
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'campaigns_campaign') THEN
        RAISE NOTICE 'Criando índice: idx_camp_tenant_status_created';
        CREATE INDEX IF NOT EXISTS idx_camp_tenant_status_created 
        ON campaigns_campaign(tenant_id, status, created_at DESC);
        
        RAISE NOTICE 'Criando índice: idx_camp_tenant_active';
        CREATE INDEX IF NOT EXISTS idx_camp_tenant_active 
        ON campaigns_campaign(tenant_id, status) 
        WHERE status IN ('active', 'paused', 'scheduled');
    ELSE
        RAISE NOTICE '⚠️  Tabela campaigns_campaign não existe - pulando';
    END IF;
    
    -- CampaignContact
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'campaigns_campaigncontact') THEN
        RAISE NOTICE 'Criando índice: idx_cc_campaign_status';
        CREATE INDEX IF NOT EXISTS idx_cc_campaign_status 
        ON campaigns_campaigncontact(campaign_id, status);
        
        RAISE NOTICE 'Criando índice: idx_cc_campaign_failed';
        CREATE INDEX IF NOT EXISTS idx_cc_campaign_failed 
        ON campaigns_campaigncontact(campaign_id, status, retry_count) 
        WHERE status = 'failed';
    ELSE
        RAISE NOTICE '⚠️  Tabela campaigns_campaigncontact não existe - pulando';
    END IF;
    
    -- CampaignLog
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'campaigns_campaignlog') THEN
        RAISE NOTICE 'Criando índice: idx_log_campaign_level_time';
        CREATE INDEX IF NOT EXISTS idx_log_campaign_level_time 
        ON campaigns_campaignlog(campaign_id, level, created_at DESC);
    ELSE
        RAISE NOTICE '⚠️  Tabela campaigns_campaignlog não existe - pulando';
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
    ELSE
        RAISE NOTICE '⚠️  Tabela chat_message não existe - pulando';
    END IF;
    
    -- Attachment
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'chat_attachment') THEN
        RAISE NOTICE 'Criando índice: idx_attach_tenant_storage';
        CREATE INDEX IF NOT EXISTS idx_attach_tenant_storage 
        ON chat_attachment(tenant_id, storage_type, expires_at);
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
    ELSE
        RAISE NOTICE '⚠️  Tabela contacts_contact não existe - pulando';
    END IF;
    
    -- ContactList
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'contacts_contactlist') THEN
        RAISE NOTICE 'Criando índice: idx_list_tenant_active';
        CREATE INDEX IF NOT EXISTS idx_list_tenant_active 
        ON contacts_contactlist(tenant_id, is_active);
    ELSE
        RAISE NOTICE '⚠️  Tabela contacts_contactlist não existe - pulando';
    END IF;
    
    -- Tag
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'contacts_tag') THEN
        RAISE NOTICE 'Criando índice: idx_tag_tenant';
        CREATE INDEX IF NOT EXISTS idx_tag_tenant 
        ON contacts_tag(tenant_id);
    ELSE
        RAISE NOTICE '⚠️  Tabela contacts_tag não existe - pulando';
    END IF;
    
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ ÍNDICES CRIADOS COM SUCESSO!';
    RAISE NOTICE '========================================';
    
END $$;


-- ============================================
-- PARTE 3: VALIDAÇÃO (Execute depois)
-- ============================================

-- Verificar índices criados
SELECT 
    'campaigns' as app,
    indexname,
    tablename,
    CASE 
        WHEN indexdef LIKE '%WHERE%' THEN 'Partial Index'
        ELSE 'Full Index'
    END as index_type
FROM pg_indexes
WHERE indexname LIKE 'idx_camp_%' 
   OR indexname LIKE 'idx_cc_%' 
   OR indexname LIKE 'idx_log_%'

UNION ALL

SELECT 
    'chat' as app,
    indexname,
    tablename,
    CASE 
        WHEN indexdef LIKE '%WHERE%' THEN 'Partial Index'
        ELSE 'Full Index'
    END as index_type
FROM pg_indexes
WHERE indexname LIKE 'idx_conv_%' 
   OR indexname LIKE 'idx_msg_%' 
   OR indexname LIKE 'idx_attach_%'

UNION ALL

SELECT 
    'contacts' as app,
    indexname,
    tablename,
    CASE 
        WHEN indexdef LIKE '%WHERE%' THEN 'Partial Index'
        ELSE 'Full Index'
    END as index_type
FROM pg_indexes
WHERE indexname LIKE 'idx_contact_%' 
   OR indexname LIKE 'idx_list_%' 
   OR indexname LIKE 'idx_tag_%'

ORDER BY app, indexname;


-- Ver tamanho dos novos índices
SELECT 
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE indexrelname LIKE 'idx_camp_%' 
   OR indexrelname LIKE 'idx_cc_%'
   OR indexrelname LIKE 'idx_log_%'
   OR indexrelname LIKE 'idx_conv_%'
   OR indexrelname LIKE 'idx_msg_%'
   OR indexrelname LIKE 'idx_attach_%'
   OR indexrelname LIKE 'idx_contact_%'
   OR indexrelname LIKE 'idx_list_%'
   OR indexrelname LIKE 'idx_tag_%'
ORDER BY pg_relation_size(indexrelid) DESC;


-- ============================================
-- ROLLBACK (Use apenas se necessário)
-- ============================================

/*
-- ATENÇÃO: Isso vai remover TODOS os índices criados
-- Execute apenas se precisar reverter completamente

DROP INDEX IF EXISTS idx_camp_tenant_status_created;
DROP INDEX IF EXISTS idx_camp_tenant_active;
DROP INDEX IF EXISTS idx_cc_campaign_status;
DROP INDEX IF EXISTS idx_cc_campaign_failed;
DROP INDEX IF EXISTS idx_log_campaign_level_time;

DROP INDEX IF EXISTS idx_conv_tenant_dept_status_time;
DROP INDEX IF EXISTS idx_conv_tenant_status_time;
DROP INDEX IF EXISTS idx_msg_conv_created;
DROP INDEX IF EXISTS idx_msg_conv_status_dir;
DROP INDEX IF EXISTS idx_attach_tenant_storage;

DROP INDEX IF EXISTS idx_contact_tenant_lifecycle;
DROP INDEX IF EXISTS idx_contact_tenant_opted;
DROP INDEX IF EXISTS idx_contact_tenant_state;
DROP INDEX IF EXISTS idx_contact_tenant_phone;
DROP INDEX IF EXISTS idx_list_tenant_active;
DROP INDEX IF EXISTS idx_tag_tenant;
*/

