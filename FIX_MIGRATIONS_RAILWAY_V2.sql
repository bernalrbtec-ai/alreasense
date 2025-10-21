-- ========================================================================
-- SCRIPT SQL PARA CORRIGIR MIGRATIONS E CRIAR ÍNDICES NA RAILWAY (V2)
-- ========================================================================
-- Este script limpa duplicatas e cria todos os índices de performance
-- ========================================================================

-- 1️⃣ IDENTIFICAR E REMOVER DUPLICATAS EM django_migrations
-- ========================================================================
DO $$
DECLARE
    duplicate_count INTEGER;
BEGIN
    -- Contar duplicatas
    SELECT COUNT(*) INTO duplicate_count
    FROM (
        SELECT app, name, COUNT(*) as cnt
        FROM django_migrations
        GROUP BY app, name
        HAVING COUNT(*) > 1
    ) duplicates;
    
    RAISE NOTICE '🔍 Duplicatas encontradas: %', duplicate_count;
    
    -- Remover duplicatas mantendo apenas a migration mais antiga
    DELETE FROM django_migrations a
    USING django_migrations b
    WHERE a.id > b.id
      AND a.app = b.app
      AND a.name = b.name;
    
    GET DIAGNOSTICS duplicate_count = ROW_COUNT;
    RAISE NOTICE '✅ Duplicatas removidas: %', duplicate_count;
END $$;

-- 2️⃣ ADICIONAR UNIQUE CONSTRAINT EM django_migrations
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

-- 3️⃣ REMOVER MIGRATIONS PROBLEMÁTICAS (para reaplicar corretamente)
-- ========================================================================
DELETE FROM django_migrations 
WHERE (app = 'contacts' AND name = '0003_add_performance_indexes')
   OR (app = 'campaigns' AND name = '0010_add_performance_indexes')
   OR (app = 'chat_messages' AND name = '0002_add_performance_indexes');

-- 4️⃣ CRIAR ÍNDICES PARA contacts_contact (SEM lifecycle_stage)
-- ========================================================================
DO $$
BEGIN
    -- tenant_id + phone
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_contact_tenant_phone') THEN
        CREATE INDEX idx_contact_tenant_phone ON contacts_contact(tenant_id, phone);
        RAISE NOTICE '✅ idx_contact_tenant_phone';
    ELSE
        RAISE NOTICE 'ℹ️  idx_contact_tenant_phone já existe';
    END IF;

    -- tenant_id + email
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_contact_tenant_email') THEN
        CREATE INDEX idx_contact_tenant_email ON contacts_contact(tenant_id, email);
        RAISE NOTICE '✅ idx_contact_tenant_email';
    ELSE
        RAISE NOTICE 'ℹ️  idx_contact_tenant_email já existe';
    END IF;

    -- tenant_id + is_active
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_contact_tenant_active') THEN
        CREATE INDEX idx_contact_tenant_active ON contacts_contact(tenant_id, is_active);
        RAISE NOTICE '✅ idx_contact_tenant_active';
    ELSE
        RAISE NOTICE 'ℹ️  idx_contact_tenant_active já existe';
    END IF;

    -- tenant_id + created_at
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_contact_tenant_created') THEN
        CREATE INDEX idx_contact_tenant_created ON contacts_contact(tenant_id, created_at);
        RAISE NOTICE '✅ idx_contact_tenant_created';
    ELSE
        RAISE NOTICE 'ℹ️  idx_contact_tenant_created já existe';
    END IF;

    -- tenant_id + last_purchase_date
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_contact_tenant_last_purchase') THEN
        CREATE INDEX idx_contact_tenant_last_purchase ON contacts_contact(tenant_id, last_purchase_date);
        RAISE NOTICE '✅ idx_contact_tenant_last_purchase';
    ELSE
        RAISE NOTICE 'ℹ️  idx_contact_tenant_last_purchase já existe';
    END IF;
END $$;

-- 5️⃣ CRIAR ÍNDICES PARA campaigns_campaign
-- ========================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_campaign_tenant_status') THEN
        CREATE INDEX idx_campaign_tenant_status ON campaigns_campaign(tenant_id, status);
        RAISE NOTICE '✅ idx_campaign_tenant_status';
    ELSE
        RAISE NOTICE 'ℹ️  idx_campaign_tenant_status já existe';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_campaign_tenant_created') THEN
        CREATE INDEX idx_campaign_tenant_created ON campaigns_campaign(tenant_id, created_at);
        RAISE NOTICE '✅ idx_campaign_tenant_created';
    ELSE
        RAISE NOTICE 'ℹ️  idx_campaign_tenant_created já existe';
    END IF;
END $$;

-- 6️⃣ CRIAR ÍNDICES PARA campaigns_contact
-- ========================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_campaign_contact_campaign_status') THEN
        CREATE INDEX idx_campaign_contact_campaign_status ON campaigns_contact(campaign_id, status);
        RAISE NOTICE '✅ idx_campaign_contact_campaign_status';
    ELSE
        RAISE NOTICE 'ℹ️  idx_campaign_contact_campaign_status já existe';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_campaign_contact_campaign_sent') THEN
        CREATE INDEX idx_campaign_contact_campaign_sent ON campaigns_contact(campaign_id, sent_at);
        RAISE NOTICE '✅ idx_campaign_contact_campaign_sent';
    ELSE
        RAISE NOTICE 'ℹ️  idx_campaign_contact_campaign_sent já existe';
    END IF;
END $$;

-- 7️⃣ CRIAR ÍNDICES PARA messages_message
-- ========================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_message_tenant_created') THEN
        CREATE INDEX idx_message_tenant_created ON messages_message(tenant_id, created_at);
        RAISE NOTICE '✅ idx_message_tenant_created';
    ELSE
        RAISE NOTICE 'ℹ️  idx_message_tenant_created já existe';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_message_tenant_sentiment') THEN
        CREATE INDEX idx_message_tenant_sentiment ON messages_message(tenant_id, sentiment);
        RAISE NOTICE '✅ idx_message_tenant_sentiment';
    ELSE
        RAISE NOTICE 'ℹ️  idx_message_tenant_sentiment já existe';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_message_tenant_satisfaction') THEN
        CREATE INDEX idx_message_tenant_satisfaction ON messages_message(tenant_id, satisfaction);
        RAISE NOTICE '✅ idx_message_tenant_satisfaction';
    ELSE
        RAISE NOTICE 'ℹ️  idx_message_tenant_satisfaction já existe';
    END IF;
END $$;

-- 8️⃣ VERIFICAÇÃO FINAL
-- ========================================================================
SELECT '========================================' AS "STATUS";
SELECT '✅ SCRIPT EXECUTADO COM SUCESSO!' AS "RESULTADO";
SELECT '========================================' AS "STATUS";

-- Mostrar todos os índices criados
SELECT 
    '📊 ÍNDICES CRIADOS:' AS "INFO",
    '' AS tablename,
    '' AS indexname
UNION ALL
SELECT 
    '  ' AS "INFO",
    tablename,
    indexname
FROM pg_indexes
WHERE indexname LIKE 'idx_%'
  AND schemaname = 'public'
ORDER BY tablename, indexname;

