-- ============================================
-- SCRIPTS SQL PARA ALTERAÇÕES NO BANCO REMOTO
-- ============================================
-- Execute estes scripts diretamente no PostgreSQL
-- 
-- 1. Adicionar campo default_department_id em notifications_whatsapp_instance
-- 2. Adicionar campo transfer_message em authn_department
-- ============================================

-- ============================================
-- 1. ADICIONAR default_department_id
-- ============================================
-- Adiciona campo default_department_id em notifications_whatsapp_instance
-- Se o campo já existir, o script não faz nada (IF NOT EXISTS)

DO $$
BEGIN
    -- Verificar se coluna já existe
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'notifications_whatsapp_instance' 
        AND column_name = 'default_department_id'
    ) THEN
        -- Adicionar coluna
        ALTER TABLE notifications_whatsapp_instance 
        ADD COLUMN default_department_id UUID NULL 
        REFERENCES authn_department(id) ON DELETE SET NULL;
        
        RAISE NOTICE 'Campo default_department_id adicionado com sucesso';
    ELSE
        RAISE NOTICE 'Campo default_department_id já existe';
    END IF;
    
    -- Criar índice se não existir
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'notifications_whatsapp_instance' 
        AND indexname = 'idx_whatsappinstance_default_dept'
    ) THEN
        CREATE INDEX idx_whatsappinstance_default_dept 
        ON notifications_whatsapp_instance(default_department_id);
        
        RAISE NOTICE 'Índice idx_whatsappinstance_default_dept criado com sucesso';
    ELSE
        RAISE NOTICE 'Índice idx_whatsappinstance_default_dept já existe';
    END IF;
END $$;

-- ============================================
-- 2. ADICIONAR transfer_message
-- ============================================
-- Adiciona campo transfer_message em authn_department
-- Se o campo já existir, o script não faz nada (IF NOT EXISTS)

DO $$
BEGIN
    -- Verificar se coluna já existe
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'authn_department' 
        AND column_name = 'transfer_message'
    ) THEN
        -- Adicionar coluna
        ALTER TABLE authn_department 
        ADD COLUMN transfer_message TEXT NULL;
        
        RAISE NOTICE 'Campo transfer_message adicionado com sucesso';
    ELSE
        RAISE NOTICE 'Campo transfer_message já existe';
    END IF;
END $$;

-- ============================================
-- VERIFICAÇÃO
-- ============================================
-- Execute estes SELECTs para verificar se as alterações foram aplicadas:

-- Verificar campo default_department_id
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'notifications_whatsapp_instance' 
AND column_name = 'default_department_id';

-- Verificar índice
SELECT 
    indexname, 
    indexdef
FROM pg_indexes 
WHERE tablename = 'notifications_whatsapp_instance' 
AND indexname = 'idx_whatsappinstance_default_dept';

-- Verificar campo transfer_message
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'authn_department' 
AND column_name = 'transfer_message';

-- ============================================
-- FIM
-- ============================================

