-- Reversão da migration chat 0017_flow_schema.
-- Remove as tabelas de fluxo (ordem por causa de FKs).
-- Fonte: backend/apps/chat/migrations/0017_flow_schema.py reverse_sql

DROP TABLE IF EXISTS chat_conversation_flow_state CASCADE;
DROP TABLE IF EXISTS chat_flow_edge CASCADE;
DROP TABLE IF EXISTS chat_flow_node CASCADE;
DROP TABLE IF EXISTS chat_flow CASCADE;
