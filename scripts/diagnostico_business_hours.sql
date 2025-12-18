-- ============================================================
-- DIAGNÓSTICO: Mensagem Automática Fora de Horário
-- ============================================================
-- Este script verifica todas as configurações relacionadas
-- ao envio de mensagens automáticas fora de horário.
-- ============================================================

-- 1. VERIFICAR TENANT
-- ============================================================
SELECT 
    id,
    name,
    status,
    created_at
FROM tenancy_tenant
WHERE name ILIKE '%RBTec%' OR name ILIKE '%rbtec%'
ORDER BY created_at DESC;

-- 2. VERIFICAR BUSINESS HOURS (Horários de Atendimento)
-- ============================================================
-- IMPORTANTE: Verificar se is_active = TRUE e horários configurados
SELECT 
    bh.id,
    t.name AS tenant_name,
    COALESCE(d.name, 'GERAL') AS department_name,
    bh.is_active,
    bh.timezone,
    bh.monday_enabled, bh.monday_start, bh.monday_end,
    bh.tuesday_enabled, bh.tuesday_start, bh.tuesday_end,
    bh.wednesday_enabled, bh.wednesday_start, bh.wednesday_end,
    bh.thursday_enabled, bh.thursday_start, bh.thursday_end,
    bh.friday_enabled, bh.friday_start, bh.friday_end,
    bh.saturday_enabled, bh.saturday_start, bh.saturday_end,
    bh.sunday_enabled, bh.sunday_start, bh.sunday_end,
    bh.holidays,
    bh.created_at,
    bh.updated_at
FROM chat_business_hours bh
JOIN tenancy_tenant t ON bh.tenant_id = t.id
LEFT JOIN authn_department d ON bh.department_id = d.id
WHERE t.name ILIKE '%RBTec%' OR t.name ILIKE '%rbtec%'
ORDER BY bh.updated_at DESC;

-- 3. VERIFICAR MENSAGEM AUTOMÁTICA (AfterHoursMessage)
-- ============================================================
-- IMPORTANTE: Verificar se is_active = TRUE e message_template preenchido
SELECT 
    ahm.id,
    t.name AS tenant_name,
    COALESCE(d.name, 'GERAL') AS department_name,
    ahm.is_active,
    ahm.reply_to_groups,
    LEFT(ahm.message_template, 100) AS message_preview,
    ahm.created_at,
    ahm.updated_at
FROM chat_after_hours_message ahm
JOIN tenancy_tenant t ON ahm.tenant_id = t.id
LEFT JOIN authn_department d ON ahm.department_id = d.id
WHERE t.name ILIKE '%RBTec%' OR t.name ILIKE '%rbtec%'
ORDER BY ahm.updated_at DESC;

-- 4. VERIFICAR CONFIGURAÇÃO DE TAREFA AUTOMÁTICA (AfterHoursTaskConfig)
-- ============================================================
SELECT 
    atc.id,
    t.name AS tenant_name,
    COALESCE(d.name, 'GERAL') AS department_name,
    atc.is_active,
    atc.create_task_enabled,
    atc.task_priority,
    LEFT(atc.task_title_template, 50) AS title_template,
    LEFT(atc.task_description_template, 100) AS description_preview,
    atc.created_at,
    atc.updated_at
FROM chat_after_hours_task_config atc
JOIN tenancy_tenant t ON atc.tenant_id = t.id
LEFT JOIN authn_department d ON atc.department_id = d.id
WHERE t.name ILIKE '%RBTec%' OR t.name ILIKE '%rbtec%'
ORDER BY atc.updated_at DESC;

-- 5. VERIFICAR ÚLTIMAS MENSAGENS RECEBIDAS (últimas 10)
-- ============================================================
SELECT 
    m.id AS message_id,
    m.created_at AS message_time,
    m.direction,
    m.status,
    m.content,
    c.contact_phone,
    c.contact_name,
    c.status AS conversation_status,
    t.name AS tenant_name,
    COALESCE(d.name, 'N/A') AS department_name,
    m.metadata->>'is_after_hours_auto' AS is_auto_message
FROM chat_message m
JOIN chat_conversation c ON m.conversation_id = c.id
JOIN tenancy_tenant t ON c.tenant_id = t.id
LEFT JOIN authn_department d ON c.department_id = d.id
WHERE t.name ILIKE '%RBTec%' OR t.name ILIKE '%rbtec%'
  AND m.direction = 'incoming'
  AND m.created_at >= NOW() - INTERVAL '1 hour'
ORDER BY m.created_at DESC
LIMIT 10;

-- 6. VERIFICAR MENSAGENS AUTOMÁTICAS ENVIADAS (últimas 10)
-- ============================================================
SELECT 
    m.id AS message_id,
    m.created_at AS message_time,
    m.direction,
    m.status,
    m.content,
    c.contact_phone,
    c.contact_name,
    m.metadata->>'is_after_hours_auto' AS is_auto_message,
    m.metadata->>'original_message_id' AS original_message_id,
    m.metadata->>'next_open_time' AS next_open_time
FROM chat_message m
JOIN chat_conversation c ON m.conversation_id = c.id
JOIN tenancy_tenant t ON c.tenant_id = t.id
WHERE t.name ILIKE '%RBTec%' OR t.name ILIKE '%rbtec%'
  AND m.direction = 'outgoing'
  AND m.metadata->>'is_after_hours_auto' = 'true'
  AND m.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY m.created_at DESC
LIMIT 10;

-- 7. VERIFICAR TAREFAS CRIADAS FORA DE HORÁRIO (últimas 10)
-- ============================================================
SELECT 
    task.id AS task_id,
    task.title,
    task.status,
    task.priority,
    task.due_date,
    task.created_at,
    task.metadata->>'is_after_hours_auto' AS is_after_hours,
    task.metadata->>'original_message_id' AS original_message_id,
    task.metadata->>'next_open_time' AS next_open_time,
    COALESCE(d.name, 'N/A') AS department_name
FROM contacts_task task
JOIN tenancy_tenant t ON task.tenant_id = t.id
LEFT JOIN authn_department d ON task.department_id = d.id
WHERE t.name ILIKE '%RBTec%' OR t.name ILIKE '%rbtec%'
  AND task.metadata->>'is_after_hours_auto' = 'true'
  AND task.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY task.created_at DESC
LIMIT 10;

-- 8. VERIFICAR HORÁRIO ATUAL vs HORÁRIO DE ATENDIMENTO
-- ============================================================
-- Este query mostra se ESTÁ FORA DE HORÁRIO no momento atual
WITH tenant_info AS (
    SELECT id, name
    FROM tenancy_tenant
    WHERE name ILIKE '%RBTec%' OR name ILIKE '%rbtec%'
    LIMIT 1
),
business_hours_info AS (
    SELECT 
        bh.*,
        ti.name AS tenant_name
    FROM chat_business_hours bh
    JOIN tenant_info ti ON bh.tenant_id = ti.id
    WHERE bh.is_active = TRUE
    ORDER BY bh.department_id NULLS LAST, bh.updated_at DESC
    LIMIT 1
)
SELECT 
    tenant_name,
    COALESCE(d.name, 'GERAL') AS department_name,
    is_active,
    timezone,
    -- Verificar dia atual
    CASE EXTRACT(DOW FROM NOW() AT TIME ZONE timezone)
        WHEN 0 THEN (monday_enabled, monday_start, monday_end)
        WHEN 1 THEN (tuesday_enabled, tuesday_start, tuesday_end)
        WHEN 2 THEN (wednesday_enabled, wednesday_start, wednesday_end)
        WHEN 3 THEN (thursday_enabled, thursday_start, thursday_end)
        WHEN 4 THEN (friday_enabled, friday_start, friday_end)
        WHEN 5 THEN (saturday_enabled, saturday_start, satury_end)
        WHEN 6 THEN (sunday_enabled, sunday_start, sunday_end)
    END AS day_config,
    NOW() AT TIME ZONE timezone AS current_local_time,
    EXTRACT(HOUR FROM NOW() AT TIME ZONE timezone) AS current_hour,
    EXTRACT(DOW FROM NOW() AT TIME ZONE timezone) AS current_weekday
FROM business_hours_info bh
LEFT JOIN authn_department d ON bh.department_id = d.id;

-- 9. RESUMO COMPACTO (TUDO EM UM)
-- ============================================================
SELECT 
    'BUSINESS HOURS' AS tipo,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE is_active = TRUE) AS ativos,
    COUNT(*) FILTER (WHERE is_active = FALSE) AS inativos
FROM chat_business_hours bh
JOIN tenancy_tenant t ON bh.tenant_id = t.id
WHERE t.name ILIKE '%RBTec%' OR t.name ILIKE '%rbtec%'

UNION ALL

SELECT 
    'AFTER HOURS MESSAGE' AS tipo,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE is_active = TRUE) AS ativos,
    COUNT(*) FILTER (WHERE is_active = FALSE) AS inativos
FROM chat_after_hours_message ahm
JOIN tenancy_tenant t ON ahm.tenant_id = t.id
WHERE t.name ILIKE '%RBTec%' OR t.name ILIKE '%rbtec%'

UNION ALL

SELECT 
    'AFTER HOURS TASK CONFIG' AS tipo,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE is_active = TRUE AND create_task_enabled = TRUE) AS ativos,
    COUNT(*) FILTER (WHERE is_active = FALSE OR create_task_enabled = FALSE) AS inativos
FROM chat_after_hours_task_config atc
JOIN tenancy_tenant t ON atc.tenant_id = t.id
WHERE t.name ILIKE '%RBTec%' OR t.name ILIKE '%rbtec%';

-- ============================================================
-- INSTRUÇÕES DE USO:
-- ============================================================
-- 1. Execute cada query individualmente para ver detalhes
-- 2. Query #1: Identifica o tenant_id correto
-- 3. Query #2: Verifica se business hours está ATIVO e configurado
-- 4. Query #3: Verifica se mensagem automática está ATIVA
-- 5. Query #4: Verifica se criação de tarefa está habilitada
-- 6. Query #5: Verifica últimas mensagens recebidas
-- 7. Query #6: Verifica se mensagens automáticas foram enviadas
-- 8. Query #7: Verifica se tarefas foram criadas
-- 9. Query #8: Verifica horário atual vs horário configurado
-- 10. Query #9: Resumo geral de todas as configurações
-- ============================================================


