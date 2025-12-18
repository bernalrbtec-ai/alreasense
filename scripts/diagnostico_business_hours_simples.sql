-- ============================================================
-- DIAGNÓSTICO SIMPLIFICADO: Mensagem Automática Fora de Horário
-- ============================================================
-- Versão simplificada para diagnóstico rápido
-- ============================================================

-- SUBSTITUA 'RBTec Informática' pelo nome exato do seu tenant se necessário
-- Ou use o tenant_id diretamente se souber

-- 1. VERIFICAR SE BUSINESS HOURS ESTÁ ATIVO
-- ============================================================
SELECT 
    'BUSINESS HOURS' AS configuracao,
    CASE 
        WHEN COUNT(*) = 0 THEN '❌ NÃO CONFIGURADO'
        WHEN COUNT(*) FILTER (WHERE is_active = TRUE) > 0 THEN '✅ ATIVO'
        ELSE '⚠️ CONFIGURADO MAS INATIVO'
    END AS status,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE is_active = TRUE) AS ativos
FROM chat_business_hours bh
JOIN tenancy_tenant t ON bh.tenant_id = t.id
WHERE t.name = 'RBTec Informática';

-- 2. VERIFICAR SE MENSAGEM AUTOMÁTICA ESTÁ ATIVA
-- ============================================================
SELECT 
    'MENSAGEM AUTOMÁTICA' AS configuracao,
    CASE 
        WHEN COUNT(*) = 0 THEN '❌ NÃO CONFIGURADA'
        WHEN COUNT(*) FILTER (WHERE is_active = TRUE) > 0 THEN '✅ ATIVA'
        ELSE '⚠️ CONFIGURADA MAS INATIVA'
    END AS status,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE is_active = TRUE) AS ativas,
    STRING_AGG(LEFT(message_template, 50), ' | ') AS preview_mensagens
FROM chat_after_hours_message ahm
JOIN tenancy_tenant t ON ahm.tenant_id = t.id
WHERE t.name = 'RBTec Informática';

-- 3. VERIFICAR ÚLTIMA MENSAGEM RECEBIDA E SE FOI PROCESSADA
-- ============================================================
SELECT 
    m.id AS message_id,
    m.created_at AS hora_recebida,
    m.content AS conteudo,
    c.contact_phone,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM chat_message m2 
            WHERE m2.metadata->>'is_after_hours_auto' = 'true'
            AND m2.metadata->>'original_message_id' = m.id::text
        ) THEN '✅ MENSAGEM AUTOMÁTICA ENVIADA'
        ELSE '❌ MENSAGEM AUTOMÁTICA NÃO ENVIADA'
    END AS status_processamento
FROM chat_message m
JOIN chat_conversation c ON m.conversation_id = c.id
JOIN tenancy_tenant t ON c.tenant_id = t.id
WHERE t.name = 'RBTec Informática'
  AND m.direction = 'incoming'
  AND m.created_at >= NOW() - INTERVAL '1 hour'
ORDER BY m.created_at DESC
LIMIT 5;

-- 4. VERIFICAR HORÁRIO ATUAL E SE ESTÁ FORA DE HORÁRIO
-- ============================================================
WITH tenant_bh AS (
    SELECT 
        bh.*,
        t.name AS tenant_name
    FROM chat_business_hours bh
    JOIN tenancy_tenant t ON bh.tenant_id = t.id
    WHERE t.name = 'RBTec Informática'
      AND bh.is_active = TRUE
    ORDER BY bh.department_id NULLS LAST
    LIMIT 1
)
SELECT 
    tenant_name,
    timezone,
    NOW() AT TIME ZONE timezone AS hora_atual_local,
    EXTRACT(DOW FROM NOW() AT TIME ZONE timezone) AS dia_semana,
    CASE EXTRACT(DOW FROM NOW() AT TIME ZONE timezone)
        WHEN 0 THEN (monday_enabled, monday_start, monday_end)
        WHEN 1 THEN (tuesday_enabled, tuesday_start, tuesday_end)
        WHEN 2 THEN (wednesday_enabled, wednesday_start, wednesday_end)
        WHEN 3 THEN (thursday_enabled, thursday_start, thursday_end)
        WHEN 4 THEN (friday_enabled, friday_start, friday_end)
        WHEN 5 THEN (saturday_enabled, saturday_start, saturday_end)
        WHEN 6 THEN (sunday_enabled, sunday_start, sunday_end)
    END AS configuracao_dia_atual
FROM tenant_bh;

-- 5. RESUMO COMPLETO EM UMA QUERY
-- ============================================================
SELECT 
    'RESUMO GERAL' AS secao,
    jsonb_build_object(
        'business_hours_ativo', (
            SELECT COUNT(*) > 0 
            FROM chat_business_hours bh
            JOIN tenancy_tenant t ON bh.tenant_id = t.id
            WHERE t.name = 'RBTec Informática' AND bh.is_active = TRUE
        ),
        'mensagem_automatica_ativa', (
            SELECT COUNT(*) > 0 
            FROM chat_after_hours_message ahm
            JOIN tenancy_tenant t ON ahm.tenant_id = t.id
            WHERE t.name = 'RBTec Informática' AND ahm.is_active = TRUE
        ),
        'ultima_mensagem_recebida', (
            SELECT MAX(m.created_at)
            FROM chat_message m
            JOIN chat_conversation c ON m.conversation_id = c.id
            JOIN tenancy_tenant t ON c.tenant_id = t.id
            WHERE t.name = 'RBTec Informática' 
              AND m.direction = 'incoming'
              AND m.created_at >= NOW() - INTERVAL '1 hour'
        ),
        'mensagens_automaticas_enviadas_hoje', (
            SELECT COUNT(*)
            FROM chat_message m
            JOIN chat_conversation c ON m.conversation_id = c.id
            JOIN tenancy_tenant t ON c.tenant_id = t.id
            WHERE t.name = 'RBTec Informática'
              AND m.direction = 'outgoing'
              AND m.metadata->>'is_after_hours_auto' = 'true'
              AND m.created_at >= CURRENT_DATE
        )
    ) AS dados;


