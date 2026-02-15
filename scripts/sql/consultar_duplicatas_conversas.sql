-- Consulta duplicatas de conversas: mesmo tenant + mesmo número em formatos diferentes
-- (ex.: +5511999999999 e 5511999999999@s.whatsapp.net)
-- Só leitura; não altera dados.
-- Uso: psql ... -f consultar_duplicatas_conversas.sql  ou executar no cliente SQL.

WITH conversas_com_digitos AS (
  SELECT
    c.id,
    c.tenant_id,
    c.contact_phone,
    c.contact_name,
    c.created_at,
    c.conversation_type,
    -- Normaliza para só dígitos (igual número lógico)
    regexp_replace(
      regexp_replace(
        regexp_replace(c.contact_phone, '@s\.whatsapp\.net', '', 'gi'),
        '@g\.us', '', 'gi'
      ),
      '[^0-9]', '', 'g'
    ) AS phone_digits
  FROM chat_conversation c
  WHERE c.conversation_type = 'individual'
)
SELECT
  d.tenant_id,
  t.name AS tenant_name,
  d.phone_digits AS numero_normalizado,
  COUNT(*) AS qtd_conversas,
  array_agg(d.contact_phone ORDER BY d.contact_phone) AS formatos_no_banco,
  array_agg(d.id::text ORDER BY d.contact_phone) AS conversation_ids,
  array_agg(d.contact_name ORDER BY d.contact_phone) AS nomes
FROM conversas_com_digitos d
LEFT JOIN tenancy_tenant t ON t.id = d.tenant_id
WHERE d.phone_digits != ''
  AND length(d.phone_digits) <= 15   -- ignora IDs de grupo longos
GROUP BY d.tenant_id, t.name, d.phone_digits
HAVING COUNT(*) > 1
ORDER BY qtd_conversas DESC, d.tenant_id, d.phone_digits;


-- Opcional: listar cada conversa que faz parte de alguma duplicata (detalhe linha a linha)
-- Descomente o bloco abaixo se quiser ver cada registro.

/*
WITH conversas_com_digitos AS (
  SELECT
    c.id,
    c.tenant_id,
    c.contact_phone,
    c.contact_name,
    c.created_at,
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
duplicatas AS (
  SELECT tenant_id, phone_digits
  FROM conversas_com_digitos
  WHERE phone_digits != '' AND length(phone_digits) <= 15
  GROUP BY tenant_id, phone_digits
  HAVING COUNT(*) > 1
)
SELECT
  d.tenant_id,
  t.name AS tenant_name,
  c.phone_digits AS numero_normalizado,
  c.id AS conversation_id,
  c.contact_phone,
  c.contact_name,
  c.created_at
FROM conversas_com_digitos c
JOIN duplicatas d ON d.tenant_id = c.tenant_id AND d.phone_digits = c.phone_digits
LEFT JOIN tenancy_tenant t ON t.id = c.tenant_id
ORDER BY c.tenant_id, c.phone_digits, c.contact_phone;
*/
