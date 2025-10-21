-- ========================================================================
-- SCRIPT SQL PARA CORRIGIR MIGRATIONS E CRIAR ÍNDICES NA RAILWAY
-- ========================================================================
-- Execute este SQL diretamente no PostgreSQL da Railway
-- ========================================================================

-- 1️⃣ ADICIONAR UNIQUE CONSTRAINT EM django_migrations (se não existir)
-- ========================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'django_migrations_app_name_uniq'
    ) THEN
        ALTER TABLE django_migrations 
        ADD CONSTRAINT django_migrations_app_name_uniq 
        UNIQUE (app, name);
        
        RAISE NOTICE '✅ UNIQUE constraint adicionada em django_migrations';
    ELSE
        RAISE NOTICE 'ℹ️  UNIQUE constraint já existe em django_migrations';
    END IF;
END $$;

-- 2️⃣ REMOVER MIGRATIONS PROBLEMÁTICAS (para reaplicar)
-- ========================================================================
DELETE FROM django_migrations 
WHERE (app = 'contacts' AND name = '0003_add_performance_indexes')
   OR (app = 'campaigns' AND name = '0010_add_performance_indexes')
   OR (app = 'chat_messages' AND name = '0002_add_performance_indexes');

-- Verificar remoção
SELECT '✅ Migrations removidas para reaplicação' AS status;

-- 3️⃣ CRIAR ÍNDICES PARA contacts_contact (CORRIGIDO - SEM lifecycle_stage)
-- ========================================================================
DO $$
BEGIN
    -- Índice: tenant_id + phone
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_contact_tenant_phone') THEN
        CREATE INDEX idx_contact_tenant_phone ON contacts_contact(tenant_id, phone);
        RAISE NOTICE '✅ Índice idx_contact_tenant_phone criado';
    END IF;

    -- Índice: tenant_id + email
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_contact_tenant_email') THEN
        CREATE INDEX idx_contact_tenant_email ON contacts_contact(tenant_id, email);
        RAISE NOTICE '✅ Índice idx_contact_tenant_email criado';
    END IF;

    -- Índice: tenant_id + is_active
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_contact_tenant_active') THEN
        CREATE INDEX idx_contact_tenant_active ON contacts_contact(tenant_id, is_active);
        RAISE NOTICE '✅ Índice idx_contact_tenant_active criado';
    END IF;

    -- Índice: tenant_id + created_at
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_contact_tenant_created') THEN
        CREATE INDEX idx_contact_tenant_created ON contacts_contact(tenant_id, created_at);
        RAISE NOTICE '✅ Índice idx_contact_tenant_created criado';
    END IF;

    -- Índice: tenant_id + last_purchase_date
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_contact_tenant_last_purchase') THEN
        CREATE INDEX idx_contact_tenant_last_purchase ON contacts_contact(tenant_id, last_purchase_date);
        RAISE NOTICE '✅ Índice idx_contact_tenant_last_purchase criado';
    END IF;
END $$;

-- 4️⃣ CRIAR ÍNDICES PARA campaigns_campaign
-- ========================================================================
DO $$
BEGIN
    -- Índice: tenant_id + status
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_campaign_tenant_status') THEN
        CREATE INDEX idx_campaign_tenant_status ON campaigns_campaign(tenant_id, status);
        RAISE NOTICE '✅ Índice idx_campaign_tenant_status criado';
    END IF;

    -- Índice: tenant_id + created_at
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_campaign_tenant_created') THEN
        CREATE INDEX idx_campaign_tenant_created ON campaigns_campaign(tenant_id, created_at);
        RAISE NOTICE '✅ Índice idx_campaign_tenant_created criado';
    END IF;
END $$;

-- 5️⃣ CRIAR ÍNDICES PARA campaigns_contact (NÃO campaigns_campaigncontact)
-- ========================================================================
DO $$
BEGIN
    -- Índice: campaign_id + status
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_campaign_contact_campaign_status') THEN
        CREATE INDEX idx_campaign_contact_campaign_status ON campaigns_contact(campaign_id, status);
        RAISE NOTICE '✅ Índice idx_campaign_contact_campaign_status criado';
    END IF;

    -- Índice: campaign_id + sent_at
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_campaign_contact_campaign_sent') THEN
        CREATE INDEX idx_campaign_contact_campaign_sent ON campaigns_contact(campaign_id, sent_at);
        RAISE NOTICE '✅ Índice idx_campaign_contact_campaign_sent criado';
    END IF;
END $$;

-- 6️⃣ CRIAR ÍNDICES PARA messages_message (NÃO chat_messages_message)
-- ========================================================================
DO $$
BEGIN
    -- Índice: tenant_id + created_at
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_message_tenant_created') THEN
        CREATE INDEX idx_message_tenant_created ON messages_message(tenant_id, created_at);
        RAISE NOTICE '✅ Índice idx_message_tenant_created criado';
    END IF;

    -- Índice: tenant_id + sentiment
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_message_tenant_sentiment') THEN
        CREATE INDEX idx_message_tenant_sentiment ON messages_message(tenant_id, sentiment);
        RAISE NOTICE '✅ Índice idx_message_tenant_sentiment criado';
    END IF;

    -- Índice: tenant_id + satisfaction
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_message_tenant_satisfaction') THEN
        CREATE INDEX idx_message_tenant_satisfaction ON messages_message(tenant_id, satisfaction);
        RAISE NOTICE '✅ Índice idx_message_tenant_satisfaction criado';
    END IF;
END $$;

-- 7️⃣ VERIFICAÇÃO FINAL
-- ========================================================================
SELECT '======================================' AS divisor;
SELECT '✅ TODOS OS ÍNDICES CRIADOS COM SUCESSO!' AS status;
SELECT '======================================' AS divisor;

-- Listar todos os índices criados
SELECT 
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE indexname LIKE 'idx_%'
ORDER BY tablename, indexname;

