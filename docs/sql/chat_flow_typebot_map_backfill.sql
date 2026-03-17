-- Backfill: copiar vínculos existentes de public.chat_flow para public.chat_flow_typebot_map
-- Requer que public.tenancy_typebot_workspace já exista e esteja populada.
-- PostgreSQL

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO public.chat_flow_typebot_map (
  id,
  tenant_id,
  flow_id,
  typebot_workspace_id,
  typebot_internal_id,
  typebot_public_id,
  bot_name,
  status,
  created_at,
  updated_at
)
SELECT
  gen_random_uuid() AS id,
  f.tenant_id,
  f.id AS flow_id,
  tw.workspace_id AS typebot_workspace_id,
  COALESCE(NULLIF(TRIM(f.typebot_internal_id), ''), NULLIF(TRIM(f.typebot_public_id), '')) AS typebot_internal_id,
  COALESCE(NULLIF(TRIM(f.typebot_public_id), ''), '') AS typebot_public_id,
  LEFT(COALESCE(NULLIF(TRIM(f.name), ''), 'Fluxo'), 255) AS bot_name,
  'active' AS status,
  NOW() AS created_at,
  NOW() AS updated_at
FROM public.chat_flow f
JOIN public.tenancy_typebot_workspace tw
  ON tw.tenant_id = f.tenant_id
WHERE
  COALESCE(NULLIF(TRIM(f.typebot_internal_id), ''), NULLIF(TRIM(f.typebot_public_id), '')) IS NOT NULL
ON CONFLICT (tenant_id, flow_id) DO UPDATE
SET
  typebot_workspace_id = EXCLUDED.typebot_workspace_id,
  typebot_internal_id  = EXCLUDED.typebot_internal_id,
  typebot_public_id    = EXCLUDED.typebot_public_id,
  bot_name             = EXCLUDED.bot_name,
  status               = EXCLUDED.status,
  updated_at           = NOW();

COMMIT;

