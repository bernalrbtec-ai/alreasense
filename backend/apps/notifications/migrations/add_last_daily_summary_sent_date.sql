-- Migration: Adicionar campo last_daily_summary_sent_date para evitar duplicação de resumos diários
-- Data: 2025-11-25
-- Descrição: Adiciona campo para rastrear quando foi enviado o último resumo diário,
--             permitindo lock individual dentro do loop (mesma lógica do lembrete de 15min)

-- Adicionar campo em UserNotificationPreferences
ALTER TABLE notifications_user_notification_preferences
ADD COLUMN IF NOT EXISTS last_daily_summary_sent_date DATE NULL;

COMMENT ON COLUMN notifications_user_notification_preferences.last_daily_summary_sent_date IS 'Data do último resumo enviado - usado para evitar duplicação entre workers';

-- Adicionar campo em DepartmentNotificationPreferences
ALTER TABLE notifications_department_notification_preferences
ADD COLUMN IF NOT EXISTS last_daily_summary_sent_date DATE NULL;

COMMENT ON COLUMN notifications_department_notification_preferences.last_daily_summary_sent_date IS 'Data do último resumo enviado - usado para evitar duplicação entre workers';

-- Criar índices para melhorar performance das queries de lock
CREATE INDEX IF NOT EXISTS idx_user_notif_pref_last_sent_date 
ON notifications_user_notification_preferences(last_daily_summary_sent_date);

CREATE INDEX IF NOT EXISTS idx_dept_notif_pref_last_sent_date 
ON notifications_department_notification_preferences(last_daily_summary_sent_date);

