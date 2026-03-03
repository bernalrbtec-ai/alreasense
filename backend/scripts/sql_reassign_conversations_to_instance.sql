-- =============================================================================
-- Reatribuir conversas órfãs à instância ativa do tenant (instância removida)
-- =============================================================================
-- Versão em um único arquivo. Recomendado usar os scripts separados:
--   sql_reassign_conversations_01_consulta.sql  (rodar primeiro)
--   sql_reassign_conversations_02_update.sql   (rodar depois de conferir)
--
-- Substitua antes de rodar:
--   tenant_id   = UUID do tenant (ex: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890')
--   instance_id = (opcional) NULL = única ativa do tenant; ou UUID da instância alvo
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1) CONSULTA — Conversas órfãs e para qual instância serão reatribuídas
-- -----------------------------------------------------------------------------
-- Defina a instância alvo: use o UUID da instância OU deixe NULL para usar
-- a única instância ativa do tenant (se houver mais de uma, a query não retorna nada).

WITH params AS (
  SELECT
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890'::uuid AS tenant_id,   -- ALTERE: UUID do tenant
    NULL::uuid AS instance_id   -- ALTERE: NULL = única ativa do tenant; ou UUID da instância alvo
),
-- Todas as instâncias ativas (incluir mesmo com instance_name vazio, para match por evolution/phone_number_id)
valid AS (
  SELECT
    wi.tenant_id,
    TRIM(COALESCE(wi.instance_name, '')) AS instance_name,
    TRIM(COALESCE(wi.evolution_instance_name, '')) AS evolution_name,
    TRIM(COALESCE(wi.phone_number_id, '')) AS phone_number_id
  FROM notifications_whatsapp_instance wi
  INNER JOIN params p ON p.tenant_id = wi.tenant_id
  WHERE wi.is_active = true
),
-- Instância alvo: a indicada em params OU a única ativa do tenant
target AS (
  SELECT
    wi.id,
    wi.tenant_id,
    wi.instance_name,
    wi.friendly_name
  FROM notifications_whatsapp_instance wi
  INNER JOIN params p ON p.tenant_id = wi.tenant_id
  WHERE wi.is_active = true
    AND (
      (p.instance_id IS NOT NULL AND wi.id = p.instance_id)
      OR
      (p.instance_id IS NULL AND (
        SELECT COUNT(*) FROM notifications_whatsapp_instance w2
        WHERE w2.tenant_id = p.tenant_id AND w2.is_active = true
      ) = 1)
    )
  LIMIT 1
),
-- Conversas órfãs: têm instance_name mas não batem com nenhuma instância ativa
orphans AS (
  SELECT
    c.id AS conversation_id,
    c.tenant_id,
    c.contact_phone,
    c.contact_name,
    c.instance_name AS old_instance_name,
    c.instance_friendly_name AS old_instance_friendly_name,
    c.last_message_at,
    t.id AS target_instance_id,
    t.instance_name AS new_instance_name,
    COALESCE(NULLIF(TRIM(t.friendly_name), ''), t.instance_name) AS new_instance_friendly_name
  FROM chat_conversation c
  INNER JOIN params p ON p.tenant_id = c.tenant_id
  CROSS JOIN target t
  WHERE TRIM(COALESCE(c.instance_name, '')) != ''
    AND NOT EXISTS (
      SELECT 1 FROM valid v
      WHERE v.tenant_id = c.tenant_id
        AND (
          (v.instance_name != '' AND TRIM(c.instance_name) = v.instance_name)
          OR (v.evolution_name != '' AND TRIM(c.instance_name) = v.evolution_name)
          OR (v.phone_number_id != '' AND TRIM(c.instance_name) = v.phone_number_id)
        )
    )
)
SELECT
  conversation_id,
  contact_phone,
  contact_name,
  old_instance_name,
  old_instance_friendly_name,
  new_instance_name,
  new_instance_friendly_name,
  last_message_at
FROM orphans
ORDER BY last_message_at DESC NULLS LAST;

-- Se quiser só a contagem (sem detalhes):
-- SELECT COUNT(*) AS total_orphans FROM orphans;


-- -----------------------------------------------------------------------------
-- 2) UPDATE — Efetivar: atualizar conversas órfãs para a instância alvo
-- -----------------------------------------------------------------------------
-- Use os MESMOS tenant_id e instance_id da consulta acima.
-- (Descomente e rode após conferir o resultado da consulta.)

/*
WITH params AS (
  SELECT 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'::uuid AS tenant_id, NULL::uuid AS instance_id
),
valid AS (
  SELECT wi.tenant_id, TRIM(COALESCE(wi.instance_name,'')) AS instance_name,
         TRIM(COALESCE(wi.evolution_instance_name,'')) AS evolution_name,
         TRIM(COALESCE(wi.phone_number_id,'')) AS phone_number_id
  FROM notifications_whatsapp_instance wi
  INNER JOIN params p ON p.tenant_id = wi.tenant_id
  WHERE wi.is_active = true
),
target AS (
  SELECT wi.id, wi.tenant_id, wi.instance_name, wi.friendly_name
  FROM notifications_whatsapp_instance wi
  INNER JOIN params p ON p.tenant_id = wi.tenant_id
  WHERE wi.is_active = true
    AND ((p.instance_id IS NOT NULL AND wi.id = p.instance_id)
         OR (p.instance_id IS NULL AND (SELECT COUNT(*) FROM notifications_whatsapp_instance w2 WHERE w2.tenant_id = p.tenant_id AND w2.is_active = true) = 1))
  LIMIT 1
),
orphan_ids AS (
  SELECT c.id FROM chat_conversation c
  INNER JOIN params p ON p.tenant_id = c.tenant_id
  CROSS JOIN target t
  WHERE TRIM(COALESCE(c.instance_name, '')) != ''
    AND NOT EXISTS (SELECT 1 FROM valid v WHERE v.tenant_id = c.tenant_id
      AND ((v.instance_name != '' AND TRIM(c.instance_name) = v.instance_name)
           OR (v.evolution_name != '' AND TRIM(c.instance_name) = v.evolution_name)
           OR (v.phone_number_id != '' AND TRIM(c.instance_name) = v.phone_number_id)))
)
UPDATE chat_conversation c
SET instance_name = t.instance_name,
    instance_friendly_name = COALESCE(NULLIF(TRIM(t.friendly_name), ''), t.instance_name),
    updated_at = NOW()
FROM orphan_ids o
CROSS JOIN target t
WHERE c.id = o.id;
*/
