-- ==========================================
-- REVERSÃO DE ÍNDICES OPCIONAIS
-- Sistema de Conversas Privadas por Usuário
-- 
-- Execute este script para remover os índices opcionais criados por
-- add_conversation_assignment_indexes.sql
-- ==========================================

BEGIN;

-- Remover índices opcionais (apenas os criados pela nova funcionalidade)
DROP INDEX IF EXISTS idx_conversation_assigned_status;
DROP INDEX IF EXISTS idx_conversation_dept_unassigned;
DROP INDEX IF EXISTS idx_conversation_my_conversations;

COMMIT;

-- ==========================================
-- VERIFICAÇÃO
-- ==========================================
-- Para verificar se índices foram removidos:
-- SELECT indexname FROM pg_indexes WHERE tablename = 'chat_conversation' AND indexname LIKE 'idx_conversation%';
