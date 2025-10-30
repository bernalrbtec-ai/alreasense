-- ========================================
-- CORRIGIR SHORT_URL DOS ATTACHMENTS
-- ========================================
-- Problema: short_url está sem /api/chat/ no path
-- Correto: https://alreasense-backend-production.up.railway.app/api/chat/media/{hash}
-- Errado:  https://alreasense-backend-production.up.railway.app/media/{hash}
-- ========================================

-- 1. Ver URLs erradas atual
SELECT 
    id,
    media_hash,
    short_url,
    original_filename
FROM chat_attachment
WHERE media_hash IS NOT NULL
ORDER BY created_at DESC;

-- 2. Corrigir URLs (adicionar /api/chat/)
UPDATE chat_attachment
SET short_url = REPLACE(short_url, '/media/', '/api/chat/media/')
WHERE media_hash IS NOT NULL
AND short_url NOT LIKE '%/api/chat/media/%';

-- 3. Verificar se funcionou
SELECT 
    id,
    media_hash,
    short_url,
    original_filename,
    'CORRETO ✅' as status
FROM chat_attachment
WHERE media_hash IS NOT NULL
AND short_url LIKE '%/api/chat/media/%'
ORDER BY created_at DESC;

