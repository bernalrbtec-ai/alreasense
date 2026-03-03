-- =============================================================================
-- 1) CONSULTA — Ver o que será alterado (rode primeiro e confira)
-- =============================================================================
-- Reatribuição de conversas órfãs (instance_name de instância removida) para
-- a instância ativa do tenant.
--
-- ANTES DE RODAR, altere no CTE "params" abaixo:
--   tenant_id   = UUID do tenant
--   instance_id = NULL para usar a única instância ativa do tenant;
--                 ou UUID da instância alvo (se o tenant tiver mais de uma)
-- =============================================================================

WITH params AS (
  SELECT
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890'::uuid AS tenant_id,   -- ALTERE
    NULL::uuid AS instance_id   -- ALTERE: NULL = única ativa; ou UUID da instância alvo
),
-- Todas as instâncias ativas do tenant (incluir mesmo com instance_name vazio, para match por evolution_instance_name/phone_number_id)
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
orphans AS (
  SELECT
    c.id AS conversation_id,
    c.tenant_id,
    c.contact_phone,
    c.contact_name,
    c.instance_name AS old_instance_name,
    c.instance_friendly_name AS old_instance_friendly_name,
    c.last_message_at,
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

-- Para só contar quantas conversas seriam alteradas (opcional):
-- WITH params AS (SELECT '...'::uuid AS tenant_id, NULL::uuid AS instance_id),
-- ... (repetir CTEs valid, target, orphans)
-- SELECT COUNT(*) AS total_a_alterar FROM orphans;
