-- Resetar last_daily_summary_sent_date para permitir novo envio
-- Isso permite que o scheduler tente enviar novamente

UPDATE notifications_user_notification_preferences
SET last_daily_summary_sent_date = NULL
WHERE daily_summary_enabled = true
  AND daily_summary_time IS NOT NULL
  AND user_id IN (
    SELECT id FROM authn_user WHERE email = 'paulo.bernal@rbtec.com.br'
  );

-- Verificar resultado
SELECT 
    u.email,
    pref.daily_summary_time,
    pref.last_daily_summary_sent_date,
    pref.daily_summary_enabled
FROM notifications_user_notification_preferences pref
JOIN authn_user u ON pref.user_id = u.id
WHERE u.email = 'paulo.bernal@rbtec.com.br'
  AND pref.daily_summary_enabled = true;

