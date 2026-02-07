-- ============================================================================
-- MARCAR MIGRATIONS COMO APLICADAS NO DJANGO
-- Execute APENAS após confirmar que as colunas foram criadas no banco
-- ============================================================================

-- Verificar se as migrations já estão marcadas
SELECT app, name, applied 
FROM django_migrations 
WHERE app IN ('chat', 'ai')
  AND name IN (
    '0015_add_transcription_quality_fields',
    '0007_add_quality_latency_model_fields'
  )
ORDER BY app, applied DESC;

-- Marcar as migrations como aplicadas
-- ATENÇÃO: Só execute se as colunas foram criadas com sucesso!

INSERT INTO django_migrations (app, name, applied)
VALUES 
    ('chat', '0015_add_transcription_quality_fields', NOW()),
    ('ai', '0007_add_quality_latency_model_fields', NOW())
ON CONFLICT (app, name) DO NOTHING;

-- Verificar se foram inseridas corretamente
SELECT app, name, applied 
FROM django_migrations 
WHERE app IN ('chat', 'ai')
  AND name IN (
    '0015_add_transcription_quality_fields',
    '0007_add_quality_latency_model_fields'
  )
ORDER BY app, applied DESC;

-- ============================================================================
-- FIM
-- ============================================================================
