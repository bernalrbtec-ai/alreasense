-- Migration: Adicionar tabela de configuração do Menu de Boas-Vindas
-- Data: 2025-12-09
-- Descrição: Tabela para armazenar configurações do menu automático de boas-vindas

DO $$
BEGIN
    -- Criar tabela se não existir
    IF NOT EXISTS (SELECT FROM pg_tables WHERE tablename = 'chat_welcome_menu_config') THEN
        CREATE TABLE chat_welcome_menu_config (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            welcome_message TEXT NOT NULL DEFAULT '',
            show_close_option BOOLEAN NOT NULL DEFAULT TRUE,
            close_option_text VARCHAR(50) NOT NULL DEFAULT 'Encerrar',
            send_to_new_conversations BOOLEAN NOT NULL DEFAULT TRUE,
            send_to_closed_conversations BOOLEAN NOT NULL DEFAULT TRUE,
            ai_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT chat_welcome_menu_config_tenant_id_fkey 
                FOREIGN KEY (tenant_id) REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
            CONSTRAINT chat_welcome_menu_config_tenant_id_unique UNIQUE (tenant_id)
        );
    END IF;

    -- Criar tabela de relacionamento Many-to-Many se não existir
    IF NOT EXISTS (SELECT FROM pg_tables WHERE tablename = 'chat_welcome_menu_config_departments') THEN
        CREATE TABLE chat_welcome_menu_config_departments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            welcomemenuconfig_id UUID NOT NULL,
            department_id UUID NOT NULL,
            CONSTRAINT chat_welcome_menu_config_departments_welcomemenuconfig_id_fkey 
                FOREIGN KEY (welcomemenuconfig_id) REFERENCES chat_welcome_menu_config(id) ON DELETE CASCADE,
            CONSTRAINT chat_welcome_menu_config_departments_department_id_fkey 
                FOREIGN KEY (department_id) REFERENCES authn_department(id) ON DELETE CASCADE,
            CONSTRAINT chat_welcome_menu_config_departments_unique 
                UNIQUE (welcomemenuconfig_id, department_id)
        );
    END IF;

    -- Índices para performance
    CREATE INDEX IF NOT EXISTS idx_chat_welcome_menu_config_tenant ON chat_welcome_menu_config(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_chat_welcome_menu_config_enabled ON chat_welcome_menu_config(enabled);
    CREATE INDEX IF NOT EXISTS idx_chat_welcome_menu_config_departments_config ON chat_welcome_menu_config_departments(welcomemenuconfig_id);
    CREATE INDEX IF NOT EXISTS idx_chat_welcome_menu_config_departments_dept ON chat_welcome_menu_config_departments(department_id);

    -- Comentários
    COMMENT ON TABLE chat_welcome_menu_config IS 'Configuração do Menu de Boas-Vindas Automático por tenant';
    COMMENT ON COLUMN chat_welcome_menu_config.enabled IS 'Se True, envia menu automático para conversas novas/fechadas';
    COMMENT ON COLUMN chat_welcome_menu_config.ai_enabled IS '⚠️ BLOQUEADO: Usar IA para processar respostas (addon futuro)';
END $$;

