-- =====================================================
-- SQL para criar tabelas de Preferências de Notificação
-- Sistema de Notificações Personalizadas
-- =====================================================
-- 
-- Execute este script diretamente no PostgreSQL
-- 
-- IMPORTANTE: 
-- - Verifique se as tabelas authn_user e tenancy_tenant existem
-- - Verifique se a tabela authn_department existe (para DepartmentNotificationPreferences)
-- - Este script usa IF NOT EXISTS para evitar erros se já existir
-- =====================================================

-- =====================================================
-- 1. TABELA: notifications_user_notification_preferences
-- =====================================================

CREATE TABLE IF NOT EXISTS notifications_user_notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    tenant_id UUID NOT NULL,
    
    -- Horários de resumo diário
    daily_summary_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    daily_summary_time TIME NULL,
    
    -- Lembrete de agenda
    agenda_reminder_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    agenda_reminder_time TIME NULL,
    
    -- Tipos de notificação
    notify_pending BOOLEAN NOT NULL DEFAULT TRUE,
    notify_in_progress BOOLEAN NOT NULL DEFAULT TRUE,
    notify_status_changes BOOLEAN NOT NULL DEFAULT TRUE,
    notify_completed BOOLEAN NOT NULL DEFAULT FALSE,
    notify_overdue BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Canais de notificação
    notify_via_whatsapp BOOLEAN NOT NULL DEFAULT TRUE,
    notify_via_websocket BOOLEAN NOT NULL DEFAULT TRUE,
    notify_via_email BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Metadados
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys
    CONSTRAINT fk_user_notif_pref_user 
        FOREIGN KEY (user_id) 
        REFERENCES authn_user(id) 
        ON DELETE CASCADE,
    
    CONSTRAINT fk_user_notif_pref_tenant 
        FOREIGN KEY (tenant_id) 
        REFERENCES tenancy_tenant(id) 
        ON DELETE CASCADE,
    
    -- Unique constraint
    CONSTRAINT unique_user_tenant_notif_pref 
        UNIQUE (user_id, tenant_id)
);

-- Índices para notifications_user_notification_preferences
CREATE INDEX IF NOT EXISTS idx_user_notif_pref_user_tenant 
    ON notifications_user_notification_preferences(user_id, tenant_id);

CREATE INDEX IF NOT EXISTS idx_user_notif_pref_daily_summary 
    ON notifications_user_notification_preferences(daily_summary_enabled, daily_summary_time) 
    WHERE daily_summary_enabled = TRUE;

CREATE INDEX IF NOT EXISTS idx_user_notif_pref_agenda_reminder 
    ON notifications_user_notification_preferences(agenda_reminder_enabled, agenda_reminder_time) 
    WHERE agenda_reminder_enabled = TRUE;

-- =====================================================
-- 2. TABELA: notifications_department_notification_preferences
-- =====================================================

CREATE TABLE IF NOT EXISTS notifications_department_notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    
    -- Horários de resumo diário
    daily_summary_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    daily_summary_time TIME NULL,
    
    -- Lembrete de agenda
    agenda_reminder_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    agenda_reminder_time TIME NULL,
    
    -- Tipos de notificação
    notify_pending BOOLEAN NOT NULL DEFAULT TRUE,
    notify_in_progress BOOLEAN NOT NULL DEFAULT TRUE,
    notify_status_changes BOOLEAN NOT NULL DEFAULT TRUE,
    notify_completed BOOLEAN NOT NULL DEFAULT FALSE,
    notify_overdue BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Filtros avançados para gestores
    notify_only_critical BOOLEAN NOT NULL DEFAULT FALSE,
    notify_only_assigned BOOLEAN NOT NULL DEFAULT FALSE,
    max_tasks_per_notification INTEGER NOT NULL DEFAULT 20,
    
    -- Canais de notificação
    notify_via_whatsapp BOOLEAN NOT NULL DEFAULT TRUE,
    notify_via_websocket BOOLEAN NOT NULL DEFAULT TRUE,
    notify_via_email BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Metadados
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_id BIGINT NULL,
    
    -- Foreign Keys
    CONSTRAINT fk_dept_notif_pref_department 
        FOREIGN KEY (department_id) 
        REFERENCES authn_department(id) 
        ON DELETE CASCADE,
    
    CONSTRAINT fk_dept_notif_pref_tenant 
        FOREIGN KEY (tenant_id) 
        REFERENCES tenancy_tenant(id) 
        ON DELETE CASCADE,
    
    CONSTRAINT fk_dept_notif_pref_created_by 
        FOREIGN KEY (created_by_id) 
        REFERENCES authn_user(id) 
        ON DELETE SET NULL,
    
    -- Unique constraint
    CONSTRAINT unique_department_tenant_notif_pref 
        UNIQUE (department_id, tenant_id)
);

-- Índices para notifications_department_notification_preferences
CREATE INDEX IF NOT EXISTS idx_dept_notif_pref_department_tenant 
    ON notifications_department_notification_preferences(department_id, tenant_id);

CREATE INDEX IF NOT EXISTS idx_dept_notif_pref_daily_summary 
    ON notifications_department_notification_preferences(daily_summary_enabled, daily_summary_time) 
    WHERE daily_summary_enabled = TRUE;

CREATE INDEX IF NOT EXISTS idx_dept_notif_pref_agenda_reminder 
    ON notifications_department_notification_preferences(agenda_reminder_enabled, agenda_reminder_time) 
    WHERE agenda_reminder_enabled = TRUE;

-- =====================================================
-- 3. COMENTÁRIOS NAS TABELAS (opcional, mas útil)
-- =====================================================

COMMENT ON TABLE notifications_user_notification_preferences IS 
    'Preferências de notificação individuais do usuário. Cada usuário pode configurar suas próprias notificações.';

COMMENT ON TABLE notifications_department_notification_preferences IS 
    'Preferências de notificação do departamento para gestores. Apenas gestores do departamento podem configurar.';

-- =====================================================
-- 4. VERIFICAÇÃO (opcional - para confirmar criação)
-- =====================================================

-- Descomente para verificar se as tabelas foram criadas:
-- SELECT 
--     table_name, 
--     column_name, 
--     data_type, 
--     is_nullable,
--     column_default
-- FROM information_schema.columns 
-- WHERE table_name IN (
--     'notifications_user_notification_preferences',
--     'notifications_department_notification_preferences'
-- )
-- ORDER BY table_name, ordinal_position;

-- =====================================================
-- FIM DO SCRIPT
-- =====================================================

