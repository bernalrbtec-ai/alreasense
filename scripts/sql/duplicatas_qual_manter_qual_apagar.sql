-- Duplicatas: qual conversa tem MAIS informações (manter) e qual APAGAR
-- Critério: mais mensagens > último last_message_at > tem contact_name > formato E.164 > created_at mais antigo
-- Uso: psql "connection_string" -f scripts/sql/duplicatas_qual_manter_qual_apagar.sql

-- Parte 1: listar duplicatas com métricas e indicação MANTER / APAGAR
WITH conversas_com_digitos AS (
  SELECT
    c.id,
    c.tenant_id,
    c.contact_phone,
    c.contact_name,
    c.created_at,
    c.last_message_at,
    c.assigned_to_id,
    c.department_id,
    regexp_replace(
      regexp_replace(
        regexp_replace(c.contact_phone, '@s\.whatsapp\.net', '', 'gi'),
        '@g\.us', '', 'gi'
      ),
      '[^0-9]', '', 'g'
    ) AS phone_digits
  FROM chat_conversation c
  WHERE c.conversation_type = 'individual'
),
contagem_mensagens AS (
  SELECT conversation_id, COUNT(*) AS msg_count
  FROM chat_message
  GROUP BY conversation_id
),
duplicatas_grupos AS (
  SELECT tenant_id, phone_digits
  FROM conversas_com_digitos
  WHERE phone_digits != '' AND length(phone_digits) <= 15
  GROUP BY tenant_id, phone_digits
  HAVING COUNT(*) > 1
),
com_metricas AS (
  SELECT
    c.id,
    c.tenant_id,
    t.name AS tenant_name,
    c.phone_digits AS numero_normalizado,
    c.contact_phone,
    c.contact_name,
    c.created_at,
    c.last_message_at,
    COALESCE(m.msg_count, 0) AS qtd_mensagens,
    (c.contact_name IS NOT NULL AND trim(c.contact_name) != '') AS tem_nome,
    (c.contact_phone LIKE '+%' AND c.contact_phone NOT LIKE '%@%') AS formato_e164,
    c.assigned_to_id,
    c.department_id
  FROM conversas_com_digitos c
  JOIN duplicatas_grupos d ON d.tenant_id = c.tenant_id AND d.phone_digits = c.phone_digits
  LEFT JOIN tenancy_tenant t ON t.id = c.tenant_id
  LEFT JOIN contagem_mensagens m ON m.conversation_id = c.id
),
ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY tenant_id, numero_normalizado
      ORDER BY
        qtd_mensagens DESC,
        last_message_at DESC NULLS LAST,
        tem_nome DESC,
        formato_e164 DESC,
        created_at ASC
    ) AS rn
  FROM com_metricas
)
SELECT
  tenant_id,
  tenant_name,
  numero_normalizado,
  id AS conversation_id,
  contact_phone,
  contact_name,
  qtd_mensagens,
  last_message_at,
  CASE WHEN rn = 1 THEN 'MANTER' ELSE 'APAGAR' END AS acao,
  rn AS ordem_ranking
FROM ranked
ORDER BY tenant_id, numero_normalizado, rn;


-- =============================================================================
-- Parte 2: Só os IDs para APAGAR (conversas com menos informações de cada grupo)
-- Copie o resultado e use no Django shell:
--   from apps.chat.models import Conversation
--   ids_apagar = ['uuid1', 'uuid2', ...]  # colar do resultado
--   n = Conversation.objects.filter(id__in=ids_apagar).delete()
--   print(n)  # (total_deleted, {model: count})
-- =============================================================================
-- Rode esta query separadamente se quiser só a lista de IDs:

WITH conversas_com_digitos AS (
  SELECT
    c.id,
    c.tenant_id,
    c.last_message_at,
    c.contact_name,
    c.contact_phone,
    regexp_replace(
      regexp_replace(
        regexp_replace(c.contact_phone, '@s\.whatsapp\.net', '', 'gi'),
        '@g\.us', '', 'gi'
      ),
      '[^0-9]', '', 'g'
    ) AS phone_digits
  FROM chat_conversation c
  WHERE c.conversation_type = 'individual'
),
contagem_mensagens AS (
  SELECT conversation_id, COUNT(*) AS msg_count FROM chat_message GROUP BY conversation_id
),
duplicatas_grupos AS (
  SELECT tenant_id, phone_digits
  FROM conversas_com_digitos
  WHERE phone_digits != '' AND length(phone_digits) <= 15
  GROUP BY tenant_id, phone_digits
  HAVING COUNT(*) > 1
),
com_metricas AS (
  SELECT
    c.id,
    c.tenant_id,
    c.phone_digits,
    c.last_message_at,
    COALESCE(m.msg_count, 0) AS qtd_mensagens,
    (c.contact_name IS NOT NULL AND trim(c.contact_name) != '') AS tem_nome,
    (c.contact_phone LIKE '+%' AND c.contact_phone NOT LIKE '%@%') AS formato_e164
  FROM conversas_com_digitos c
  JOIN duplicatas_grupos d ON d.tenant_id = c.tenant_id AND d.phone_digits = c.phone_digits
  LEFT JOIN contagem_mensagens m ON m.conversation_id = c.id
),
ranked AS (
  SELECT id, ROW_NUMBER() OVER (
    PARTITION BY tenant_id, phone_digits
    ORDER BY qtd_mensagens DESC, last_message_at DESC NULLS LAST, tem_nome DESC, formato_e164 DESC, id ASC
  ) AS rn
  FROM com_metricas
)
SELECT id AS id_conversation_apagar
FROM ranked
WHERE rn > 1
ORDER BY id;
