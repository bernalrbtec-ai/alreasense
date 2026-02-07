-- ============================================================================
-- Zerar conversas de um tenant (para testar Secretária IA com histórico limpo)
-- ============================================================================
-- 1. Para achar o tenant_id, rode: SELECT id, name FROM tenancy_tenant;
-- 2. Substitua o UUID abaixo se for outro tenant
-- 3. Execute no PostgreSQL
-- ============================================================================
-- Tenant: Alrea.ai (8e082a56-32e8-4c1d-9df6-e34975be18ad)
-- ============================================================================

-- Memória IA por conversas do tenant
DELETE FROM ai_memory_item
WHERE conversation_id IN (
  SELECT id FROM chat_conversation WHERE tenant_id = '8e082a56-32e8-4c1d-9df6-e34975be18ad'::uuid
);

-- Auditoria do gateway IA do tenant
DELETE FROM ai_gateway_audit
WHERE tenant_id = '8e082a56-32e8-4c1d-9df6-e34975be18ad'::uuid;

-- Conversas (CASCADE remove: chat_message → chat_attachment, chat_message_reaction, chat_message_edithistory)
DELETE FROM chat_conversation
WHERE tenant_id = '8e082a56-32e8-4c1d-9df6-e34975be18ad'::uuid;

-- Conferir que zerou (deve retornar 0)
-- SELECT COUNT(*) FROM chat_conversation WHERE tenant_id = '8e082a56-32e8-4c1d-9df6-e34975be18ad'::uuid;
