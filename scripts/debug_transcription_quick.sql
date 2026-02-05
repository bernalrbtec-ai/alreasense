-- QUERY RÁPIDA: Ver onde está duration_ms nos attachments com transcrição
-- Execute esta query primeiro para ver a estrutura

SELECT 
    id,
    created_at,
    -- Verificar duration em diferentes lugares
    (metadata->>'duration_ms')::bigint as metadata_duration_ms,
    (metadata->>'duration')::numeric as metadata_duration,
    (ai_metadata->>'duration_ms')::bigint as ai_metadata_duration_ms,
    (ai_metadata->>'duration')::numeric as ai_metadata_duration,
    (ai_metadata->'transcription'->>'duration_ms')::bigint as transcription_duration_ms,
    (ai_metadata->'transcription'->>'duration')::numeric as transcription_duration,
    -- Ver preview dos JSONs
    LEFT(metadata::text, 150) as metadata_preview,
    LEFT(ai_metadata::text, 150) as ai_metadata_preview
FROM chat_attachment
WHERE 
    mime_type LIKE 'audio/%'
    AND transcription IS NOT NULL 
    AND transcription != ''
ORDER BY created_at DESC
LIMIT 10;
