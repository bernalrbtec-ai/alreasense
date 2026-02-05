-- Verificar se as métricas estão sendo salvas por tenant corretamente

-- 1. Ver métricas por tenant
SELECT 
    t.id as tenant_id,
    t.name as tenant_name,
    COUNT(m.id) as total_metrics,
    SUM(m.minutes_total) as total_minutes,
    SUM(m.audio_count) as total_audios,
    MIN(m.date) as first_date,
    MAX(m.date) as last_date
FROM ai_transcription_daily_metrics m
JOIN tenancy_tenant t ON m.tenant_id = t.id
GROUP BY t.id, t.name
ORDER BY t.name;

-- 2. Ver métricas de um tenant específico (substitua o UUID)
-- SELECT * FROM ai_transcription_daily_metrics WHERE tenant_id = 'SEU-TENANT-UUID-AQUI' ORDER BY date DESC LIMIT 10;

-- 3. Verificar se há métricas sem tenant (não deveria ter)
SELECT COUNT(*) as metrics_without_tenant
FROM ai_transcription_daily_metrics
WHERE tenant_id IS NULL;
