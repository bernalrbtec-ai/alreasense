-- =============================================================================
-- Limpeza de dados Sense por telefone + tenant (PostgreSQL)
-- Equivalente conceitual a: manage.py cleanup_contact_phone
--
-- ATENÇÃO: IRREVERSÍVEL. Teste com BEGIN ... ROLLBACK antes de COMMIT.
--
-- NÃO apaga: campanhas, filas de disparo, memória no painel Dify.
-- Bloco final OPCIONAL: apagar contacts_contact (CRM), como --include-contact.
-- =============================================================================

BEGIN;

-- --------------------------------------------------------------------------- EDITAR AQUI
CREATE TEMP TABLE _sense_cleanup_tenant (tenant_id uuid PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _sense_cleanup_tenant VALUES ('a72fbca7-92cd-4aa0-80cb-1c0a02761218');

-- Só dígitos; inclua variantes com e sem código 55 (Brasil)
CREATE TEMP TABLE _sense_cleanup_phones (digits text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO _sense_cleanup_phones (digits) VALUES
  ('17991253112'),
  ('5517991253112');

-- --------------------------------------------------------------------------- Pré-visualização
SELECT
  (SELECT count(*) FROM chat_conversation c
   WHERE c.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
     AND COALESCE(c.conversation_type, 'individual') <> 'group'
     AND regexp_replace(COALESCE(c.contact_phone, ''), '[^0-9]', '', 'g')
         IN (SELECT digits FROM _sense_cleanup_phones)
  ) AS conversas_a_apagar,
  (SELECT count(*) FROM contacts_contact cc
   WHERE cc.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
     AND regexp_replace(COALESCE(cc.phone, ''), '[^0-9]', '', 'g')
         IN (SELECT digits FROM _sense_cleanup_phones)
  ) AS contatos_crm_com_esse_numero;

-- --------------------------------------------------------------------------- CTE reutilizável: conversas alvo
-- conv_ids: todas as chat_conversation 1:1 do tenant cujo telefone normalizado bate

-- 1) ai_gateway_audit
DELETE FROM ai_gateway_audit a
WHERE a.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
  AND (
    a.conversation_id IN (
      SELECT c.id
      FROM chat_conversation c
      WHERE c.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
        AND COALESCE(c.conversation_type, 'individual') <> 'group'
        AND regexp_replace(COALESCE(c.contact_phone, ''), '[^0-9]', '', 'g')
            IN (SELECT digits FROM _sense_cleanup_phones)
    )
    OR a.contact_id IN (
      SELECT cc.id
      FROM contacts_contact cc
      WHERE cc.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
        AND regexp_replace(COALESCE(cc.phone, ''), '[^0-9]', '', 'g')
            IN (SELECT digits FROM _sense_cleanup_phones)
    )
  );

-- 2) ai_triage_result
DELETE FROM ai_triage_result t
WHERE t.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
  AND t.conversation_id IN (
    SELECT c.id
    FROM chat_conversation c
    WHERE c.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
      AND COALESCE(c.conversation_type, 'individual') <> 'group'
      AND regexp_replace(COALESCE(c.contact_phone, ''), '[^0-9]', '', 'g')
          IN (SELECT digits FROM _sense_cleanup_phones)
  );

-- 3) ai_memory_item
DELETE FROM ai_memory_item m
WHERE m.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
  AND m.conversation_id IN (
    SELECT c.id
    FROM chat_conversation c
    WHERE c.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
      AND COALESCE(c.conversation_type, 'individual') <> 'group'
      AND regexp_replace(COALESCE(c.contact_phone, ''), '[^0-9]', '', 'g')
          IN (SELECT digits FROM _sense_cleanup_phones)
  );

-- 4) ai_knowledge_document (metadata JSON)
DELETE FROM ai_knowledge_document k
WHERE k.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
  AND (
    k.metadata->>'contact_phone' IN (SELECT digits FROM _sense_cleanup_phones)
    OR k.metadata->>'conversation_id' IN (
      SELECT c.id::text
      FROM chat_conversation c
      WHERE c.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
        AND COALESCE(c.conversation_type, 'individual') <> 'group'
        AND regexp_replace(COALESCE(c.contact_phone, ''), '[^0-9]', '', 'g')
            IN (SELECT digits FROM _sense_cleanup_phones)
    )
  );

-- 5) ai_conversation_summary
DELETE FROM ai_conversation_summary s
WHERE s.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
  AND (
    s.conversation_id IN (
      SELECT c.id
      FROM chat_conversation c
      WHERE c.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
        AND COALESCE(c.conversation_type, 'individual') <> 'group'
        AND regexp_replace(COALESCE(c.contact_phone, ''), '[^0-9]', '', 'g')
            IN (SELECT digits FROM _sense_cleanup_phones)
    )
    OR regexp_replace(COALESCE(s.contact_phone, ''), '[^0-9]', '', 'g')
        IN (SELECT digits FROM _sense_cleanup_phones)
  );

-- 6) ai_consolidation_record
DELETE FROM ai_consolidation_record r
WHERE r.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
  AND regexp_replace(COALESCE(r.contact_phone, ''), '[^0-9]', '', 'g')
      IN (SELECT digits FROM _sense_cleanup_phones);

-- 7) chat_conversation (CASCADE típico: chat_message, chat_attachment,
--    chat_conversation_participants, chat_flow state, ai_dify_conversation_state, …)
DELETE FROM chat_conversation c
WHERE c.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
  AND COALESCE(c.conversation_type, 'individual') <> 'group'
  AND regexp_replace(COALESCE(c.contact_phone, ''), '[^0-9]', '', 'g')
      IN (SELECT digits FROM _sense_cleanup_phones);

-- 8) OPCIONAL — mesmo efeito de --include-contact (pode falhar se campanhas
--    ou outras FKs apontarem para contacts_contact; nesse caso trate manualmente)
/*
DELETE FROM contacts_contact cc
WHERE cc.tenant_id = (SELECT tenant_id FROM _sense_cleanup_tenant)
  AND regexp_replace(COALESCE(cc.phone, ''), '[^0-9]', '', 'g')
      IN (SELECT digits FROM _sense_cleanup_phones);
*/

-- Teste: troque COMMIT por ROLLBACK para desfazer tudo nesta sessão.
COMMIT;
