-- =============================================================================
-- 2) UPDATE — Efetivar a alteração (rode DEPOIS de conferir a consulta)
-- =============================================================================
-- Atualiza conversas órfãs do tenant para a instância alvo.
-- Use os MESMOS tenant_id e instance_id que usou na consulta (script 01).
--
-- ANTES DE RODAR, altere no CTE "params" abaixo (igual ao script 01).
-- =============================================================================

WITH params AS (
  SELECT
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890'::uuid AS tenant_id,   -- ALTERE (mesmo da consulta)
    NULL::uuid AS instance_id   -- ALTERE: NULL = única ativa; ou UUID da instância alvo
),
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
  SELECT wi.id, wi.tenant_id, wi.instance_name, wi.friendly_name
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
orphan_ids AS (
  SELECT c.id
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
UPDATE chat_conversation c
SET
  instance_name = t.instance_name,
  instance_friendly_name = COALESCE(NULLIF(TRIM(t.friendly_name), ''), t.instance_name),
  updated_at = NOW()
FROM orphan_ids o
CROSS JOIN target t
WHERE c.id = o.id;
