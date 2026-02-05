-- Script SQL para debugar estrutura de attachments com transcrição
-- Mostra onde duration_ms está armazenado (ou não está)

-- 1. Ver estrutura básica de attachments com transcrição
SELECT 
    id,
    created_at,
    mime_type,
    transcription IS NOT NULL AND transcription != '' as has_transcription,
    metadata IS NOT NULL as has_metadata,
    ai_metadata IS NOT NULL as has_ai_metadata,
    -- Verificar duration em metadata
    (metadata->>'duration_ms')::bigint as metadata_duration_ms,
    (metadata->>'duration')::numeric as metadata_duration_seconds,
    -- Verificar duration em ai_metadata (raiz)
    (ai_metadata->>'duration_ms')::bigint as ai_metadata_duration_ms,
    (ai_metadata->>'duration')::numeric as ai_metadata_duration_seconds,
    -- Verificar duration em ai_metadata.transcription
    (ai_metadata->'transcription'->>'duration_ms')::bigint as transcription_duration_ms,
    (ai_metadata->'transcription'->>'duration')::numeric as transcription_duration_seconds,
    -- Ver estrutura completa de metadata (primeiros 200 chars)
    LEFT(metadata::text, 200) as metadata_preview,
    -- Ver estrutura completa de ai_metadata (primeiros 200 chars)
    LEFT(ai_metadata::text, 200) as ai_metadata_preview
FROM chat_attachment
WHERE 
    mime_type LIKE 'audio/%'
    AND transcription IS NOT NULL 
    AND transcription != ''
ORDER BY created_at DESC
LIMIT 20;

-- 2. Contar quantos têm duration em cada lugar
SELECT 
    COUNT(*) as total_with_transcription,
    COUNT(CASE WHEN metadata->>'duration_ms' IS NOT NULL THEN 1 END) as has_metadata_duration_ms,
    COUNT(CASE WHEN metadata->>'duration' IS NOT NULL THEN 1 END) as has_metadata_duration,
    COUNT(CASE WHEN ai_metadata->>'duration_ms' IS NOT NULL THEN 1 END) as has_ai_metadata_duration_ms,
    COUNT(CASE WHEN ai_metadata->>'duration' IS NOT NULL THEN 1 END) as has_ai_metadata_duration,
    COUNT(CASE WHEN ai_metadata->'transcription'->>'duration_ms' IS NOT NULL THEN 1 END) as has_transcription_duration_ms,
    COUNT(CASE WHEN ai_metadata->'transcription'->>'duration' IS NOT NULL THEN 1 END) as has_transcription_duration
FROM chat_attachment
WHERE 
    mime_type LIKE 'audio/%'
    AND transcription IS NOT NULL 
    AND transcription != '';

-- 3. Ver exemplos completos de metadata e ai_metadata (JSON completo)
SELECT 
    id,
    created_at,
    metadata::text as metadata_full,
    ai_metadata::text as ai_metadata_full
FROM chat_attachment
WHERE 
    mime_type LIKE 'audio/%'
    AND transcription IS NOT NULL 
    AND transcription != ''
ORDER BY created_at DESC
LIMIT 5;

-- 4. Ver chaves disponíveis em metadata
SELECT DISTINCT
    jsonb_object_keys(metadata) as metadata_key
FROM chat_attachment
WHERE 
    mime_type LIKE 'audio/%'
    AND metadata IS NOT NULL
    AND metadata != '{}'::jsonb
ORDER BY metadata_key;

-- 5. Ver chaves disponíveis em ai_metadata
SELECT DISTINCT
    jsonb_object_keys(ai_metadata) as ai_metadata_key
FROM chat_attachment
WHERE 
    mime_type LIKE 'audio/%'
    AND ai_metadata IS NOT NULL
    AND ai_metadata != '{}'::jsonb
ORDER BY ai_metadata_key;

-- 6. Ver chaves dentro de ai_metadata.transcription (se existir)
SELECT DISTINCT
    jsonb_object_keys(ai_metadata->'transcription') as transcription_key
FROM chat_attachment
WHERE 
    mime_type LIKE 'audio/%'
    AND ai_metadata->'transcription' IS NOT NULL
ORDER BY transcription_key;
