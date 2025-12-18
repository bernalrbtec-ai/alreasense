-- ============================================================
-- VERIFICAÇÃO ESPECÍFICA: Por que mensagem automática não foi enviada?
-- ============================================================
-- Execute este script após enviar uma mensagem fora de horário
-- ============================================================

-- 1. IDENTIFICAR TENANT E ÚLTIMA MENSAGEM RECEBIDA
-- ============================================================
WITH ultima_mensagem AS (
    SELECT 
        m.id AS message_id,
        m.created_at AS message_time,
        m.content,
        m.direction,
        m.status,
        c.id AS conversation_id,
        c.contact_phone,
        c.contact_name,
        c.department_id,
        t.id AS tenant_id,
        t.name AS tenant_name,
        COALESCE(d.name, 'GERAL') AS department_name
    FROM chat_message m
    JOIN chat_conversation c ON m.conversation_id = c.id
    JOIN tenancy_tenant t ON c.tenant_id = t.id
    LEFT JOIN authn_department d ON c.department_id = d.id
    WHERE t.name = 'RBTec Informática'
      AND m.direction = 'incoming'
    ORDER BY m.created_at DESC
    LIMIT 1
)
SELECT 
    'ÚLTIMA MENSAGEM RECEBIDA' AS secao,
    message_id,
    message_time,
    content,
    contact_phone,
    department_name,
    tenant_name
FROM ultima_mensagem;

-- 2. VERIFICAR SE BUSINESS HOURS ESTÁ ATIVO PARA ESTA MENSAGEM
-- ============================================================
WITH ultima_mensagem AS (
    SELECT 
        m.created_at AS message_time,
        c.department_id,
        t.id AS tenant_id
    FROM chat_message m
    JOIN chat_conversation c ON m.conversation_id = c.id
    JOIN tenancy_tenant t ON c.tenant_id = t.id
    WHERE t.name = 'RBTec Informática'
      AND m.direction = 'incoming'
    ORDER BY m.created_at DESC
    LIMIT 1
),
business_hours_check AS (
    SELECT 
        bh.*,
        CASE 
            WHEN bh.department_id = um.department_id THEN 'DEPARTAMENTO ESPECÍFICO'
            WHEN bh.department_id IS NULL THEN 'GERAL DO TENANT'
            ELSE 'OUTRO DEPARTAMENTO'
        END AS tipo_config
    FROM chat_business_hours bh
    CROSS JOIN ultima_mensagem um
    WHERE bh.tenant_id = um.tenant_id
      AND (bh.department_id = um.department_id OR bh.department_id IS NULL)
    ORDER BY 
        CASE WHEN bh.department_id = um.department_id THEN 1 ELSE 2 END,
        bh.updated_at DESC
    LIMIT 1
)
SELECT 
    'BUSINESS HOURS' AS secao,
    tipo_config,
    is_active,
    CASE 
        WHEN is_active = FALSE THEN '❌ DESATIVADO - Mensagens automáticas NÃO serão enviadas'
        WHEN is_active = TRUE THEN '✅ ATIVO - Mensagens automáticas PODEM ser enviadas'
    END AS status,
    timezone,
    -- Verificar dia da semana da mensagem
    EXTRACT(DOW FROM message_time AT TIME ZONE timezone) AS dia_semana_mensagem,
    CASE EXTRACT(DOW FROM message_time AT TIME ZONE timezone)
        WHEN 0 THEN (monday_enabled, monday_start, monday_end)
        WHEN 1 THEN (tuesday_enabled, tuesday_start, tuesday_end)
        WHEN 2 THEN (wednesday_enabled, wednesday_start, wednesday_end)
        WHEN 3 THEN (thursday_enabled, thursday_start, thursday_end)
        WHEN 4 THEN (friday_enabled, friday_start, friday_end)
        WHEN 5 THEN (saturday_enabled, saturday_start, saturday_end)
        WHEN 6 THEN (sunday_enabled, sunday_start, sunday_end)
    END AS configuracao_dia
FROM business_hours_check bh
CROSS JOIN ultima_mensagem um;

-- 3. VERIFICAR SE MENSAGEM AUTOMÁTICA ESTÁ CONFIGURADA E ATIVA
-- ============================================================
WITH ultima_mensagem AS (
    SELECT 
        c.department_id,
        t.id AS tenant_id
    FROM chat_message m
    JOIN chat_conversation c ON m.conversation_id = c.id
    JOIN tenancy_tenant t ON c.tenant_id = t.id
    WHERE t.name = 'RBTec Informática'
      AND m.direction = 'incoming'
    ORDER BY m.created_at DESC
    LIMIT 1
),
mensagem_config AS (
    SELECT 
        ahm.*,
        CASE 
            WHEN ahm.department_id = um.department_id THEN 'DEPARTAMENTO ESPECÍFICO'
            WHEN ahm.department_id IS NULL THEN 'GERAL DO TENANT'
            ELSE 'OUTRO DEPARTAMENTO'
        END AS tipo_config
    FROM chat_after_hours_message ahm
    CROSS JOIN ultima_mensagem um
    WHERE ahm.tenant_id = um.tenant_id
      AND (ahm.department_id = um.department_id OR ahm.department_id IS NULL)
    ORDER BY 
        CASE WHEN ahm.department_id = um.department_id THEN 1 ELSE 2 END,
        ahm.updated_at DESC
    LIMIT 1
)
SELECT 
    'MENSAGEM AUTOMÁTICA' AS secao,
    tipo_config,
    is_active,
    CASE 
        WHEN COUNT(*) = 0 THEN '❌ NÃO CONFIGURADA - Mensagem automática NÃO será enviada'
        WHEN is_active = FALSE THEN '⚠️ CONFIGURADA MAS INATIVA - Mensagem automática NÃO será enviada'
        WHEN is_active = TRUE THEN '✅ ATIVA - Mensagem automática SERÁ enviada'
    END AS status,
    reply_to_groups,
    LEFT(message_template, 200) AS preview_mensagem
FROM mensagem_config
GROUP BY tipo_config, is_active, reply_to_groups, message_template;

-- 4. VERIFICAR SE MENSAGEM AUTOMÁTICA FOI CRIADA PARA A ÚLTIMA MENSAGEM
-- ============================================================
WITH ultima_mensagem AS (
    SELECT 
        m.id AS message_id,
        m.created_at AS message_time
    FROM chat_message m
    JOIN chat_conversation c ON m.conversation_id = c.id
    JOIN tenancy_tenant t ON c.tenant_id = t.id
    WHERE t.name = 'RBTec Informática'
      AND m.direction = 'incoming'
    ORDER BY m.created_at DESC
    LIMIT 1
)
SELECT 
    'VERIFICAÇÃO DE MENSAGEM AUTOMÁTICA ENVIADA' AS secao,
    CASE 
        WHEN EXISTS (
            SELECT 1 
            FROM chat_message m2
            WHERE m2.metadata->>'is_after_hours_auto' = 'true'
            AND m2.metadata->>'original_message_id' = um.message_id::text
        ) THEN '✅ MENSAGEM AUTOMÁTICA FOI ENVIADA'
        ELSE '❌ MENSAGEM AUTOMÁTICA NÃO FOI ENVIADA'
    END AS status,
    (
        SELECT m2.id
        FROM chat_message m2
        WHERE m2.metadata->>'is_after_hours_auto' = 'true'
        AND m2.metadata->>'original_message_id' = um.message_id::text
        LIMIT 1
    ) AS mensagem_automatica_id,
    (
        SELECT m2.created_at
        FROM chat_message m2
        WHERE m2.metadata->>'is_after_hours_auto' = 'true'
        AND m2.metadata->>'original_message_id' = um.message_id::text
        LIMIT 1
    ) AS quando_enviada
FROM ultima_mensagem um;

-- 5. DIAGNÓSTICO COMPLETO EM JSON (FÁCIL DE LER)
-- ============================================================
WITH ultima_mensagem AS (
    SELECT 
        m.id AS message_id,
        m.created_at AS message_time,
        m.content,
        c.department_id,
        t.id AS tenant_id,
        t.name AS tenant_name
    FROM chat_message m
    JOIN chat_conversation c ON m.conversation_id = c.id
    JOIN tenancy_tenant t ON c.tenant_id = t.id
    WHERE t.name = 'RBTec Informática'
      AND m.direction = 'incoming'
    ORDER BY m.created_at DESC
    LIMIT 1
),
bh_check AS (
    SELECT 
        bh.is_active AS bh_ativo,
        bh.timezone
    FROM chat_business_hours bh
    CROSS JOIN ultima_mensagem um
    WHERE bh.tenant_id = um.tenant_id
      AND (bh.department_id = um.department_id OR bh.department_id IS NULL)
    ORDER BY 
        CASE WHEN bh.department_id = um.department_id THEN 1 ELSE 2 END
    LIMIT 1
),
msg_check AS (
    SELECT 
        ahm.is_active AS msg_ativa,
        ahm.message_template IS NOT NULL AS msg_configurada
    FROM chat_after_hours_message ahm
    CROSS JOIN ultima_mensagem um
    WHERE ahm.tenant_id = um.tenant_id
      AND (ahm.department_id = um.department_id OR ahm.department_id IS NULL)
    ORDER BY 
        CASE WHEN ahm.department_id = um.department_id THEN 1 ELSE 2 END
    LIMIT 1
),
auto_msg_check AS (
    SELECT 
        EXISTS (
            SELECT 1 
            FROM chat_message m2
            CROSS JOIN ultima_mensagem um
            WHERE m2.metadata->>'is_after_hours_auto' = 'true'
            AND m2.metadata->>'original_message_id' = um.message_id::text
        ) AS foi_enviada
)
SELECT 
    jsonb_pretty(
        jsonb_build_object(
            'ultima_mensagem', (
                SELECT jsonb_build_object(
                    'id', message_id,
                    'hora', message_time,
                    'conteudo', LEFT(content, 100)
                )
                FROM ultima_mensagem
            ),
            'business_hours', (
                SELECT jsonb_build_object(
                    'ativo', COALESCE(bh_ativo, false),
                    'timezone', COALESCE(timezone, 'N/A'),
                    'status', CASE 
                        WHEN bh_ativo = TRUE THEN '✅ ATIVO'
                        WHEN bh_ativo = FALSE THEN '❌ DESATIVADO'
                        ELSE '❌ NÃO CONFIGURADO'
                    END
                )
                FROM bh_check
            ),
            'mensagem_automatica', (
                SELECT jsonb_build_object(
                    'configurada', COALESCE(msg_configurada, false),
                    'ativa', COALESCE(msg_ativa, false),
                    'status', CASE 
                        WHEN msg_configurada = FALSE THEN '❌ NÃO CONFIGURADA'
                        WHEN msg_ativa = FALSE THEN '⚠️ CONFIGURADA MAS INATIVA'
                        WHEN msg_ativa = TRUE THEN '✅ ATIVA'
                        ELSE '❌ NÃO CONFIGURADA'
                    END
                )
                FROM msg_check
            ),
            'mensagem_enviada', (
                SELECT jsonb_build_object(
                    'foi_enviada', COALESCE(foi_enviada, false),
                    'status', CASE 
                        WHEN foi_enviada = TRUE THEN '✅ MENSAGEM AUTOMÁTICA FOI ENVIADA'
                        ELSE '❌ MENSAGEM AUTOMÁTICA NÃO FOI ENVIADA'
                    END
                )
                FROM auto_msg_check
            ),
            'diagnostico', (
                SELECT 
                    CASE 
                        WHEN bh_ativo = FALSE THEN '❌ PROBLEMA: Business Hours está DESATIVADO (is_active = FALSE)'
                        WHEN msg_configurada = FALSE THEN '❌ PROBLEMA: Mensagem automática NÃO está configurada'
                        WHEN msg_ativa = FALSE THEN '❌ PROBLEMA: Mensagem automática está INATIVA (is_active = FALSE)'
                        WHEN foi_enviada = FALSE THEN '⚠️ ATENÇÃO: Configurações OK mas mensagem não foi enviada. Verifique logs do backend.'
                        ELSE '✅ TUDO OK'
                    END
                FROM bh_check, msg_check, auto_msg_check
            )
        )
    ) AS diagnostico_completo;


