-- Script para verificar e corrigir isolamento de métricas por tenant

-- 1. Ver métricas por tenant (verificar se há dados misturados)
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

-- 2. Verificar se há métricas com tenant_id incorreto
-- (comparar com attachments reais do tenant)
SELECT 
    m.tenant_id,
    t.name as tenant_name,
    m.date,
    m.audio_count as metrics_audio_count,
    COUNT(DISTINCT a.id) as actual_audio_count
FROM ai_transcription_daily_metrics m
JOIN tenancy_tenant t ON m.tenant_id = t.id
LEFT JOIN chat_attachment a ON 
    a.tenant_id = m.tenant_id
    AND DATE(a.created_at AT TIME ZONE 'UTC') = m.date
    AND a.mime_type LIKE 'audio/%'
    AND a.transcription IS NOT NULL
    AND a.transcription != ''
GROUP BY m.tenant_id, t.name, m.date, m.audio_count
HAVING COUNT(DISTINCT a.id) != m.audio_count
ORDER BY m.date DESC
LIMIT 20;

-- 3. DELETAR todas as métricas e refazer (CUIDADO: execute apenas se tiver certeza)
-- DELETE FROM ai_transcription_daily_metrics;

-- 4. Rebuild manual por tenant (execute via Django management command)
-- python manage.py rebuild_transcription_metrics --tenant <TENANT-UUID> --from 2026-01-01 --to 2026-02-05
