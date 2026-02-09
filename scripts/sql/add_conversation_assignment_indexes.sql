-- ==========================================
-- ÍNDICES OPCIONAIS PARA PERFORMANCE
-- Sistema de Conversas Privadas por Usuário
-- 
-- ⚠️ IMPORTANTE: Aplicar apenas se monitoramento mostrar necessidade
-- Estes índices são OPCIONAIS e podem melhorar performance de queries específicas
-- ==========================================

BEGIN;

-- Índice composto para filtrar conversas atribuídas a usuário específico
-- Útil para query: assigned_to=X AND status='open'
-- Melhora performance da aba "Minhas Conversas"
CREATE INDEX IF NOT EXISTS idx_conversation_assigned_status 
ON chat_conversation(assigned_to_id, status) 
WHERE assigned_to_id IS NOT NULL;

-- Índice composto para filtrar conversas não atribuídas por departamento
-- Útil para query: department=X AND assigned_to IS NULL AND status='pending'
-- Melhora performance ao filtrar conversas disponíveis no departamento
CREATE INDEX IF NOT EXISTS idx_conversation_dept_unassigned 
ON chat_conversation(department_id, status) 
WHERE assigned_to_id IS NULL AND status IN ('pending', 'open');

-- Índice composto para "Minhas Conversas" (assigned_to + status + last_message_at)
-- Útil para query: assigned_to=X AND status='open' ORDER BY last_message_at DESC
-- Melhora performance da ordenação na aba "Minhas Conversas"
CREATE INDEX IF NOT EXISTS idx_conversation_my_conversations 
ON chat_conversation(assigned_to_id, status, last_message_at DESC NULLS LAST) 
WHERE assigned_to_id IS NOT NULL AND status = 'open';

COMMIT;

-- ==========================================
-- VERIFICAÇÃO
-- ==========================================
-- Para verificar se índices foram criados:
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'chat_conversation' AND indexname LIKE 'idx_conversation%';
--
-- Para verificar tamanho dos índices:
-- SELECT 
--     indexname,
--     pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
-- FROM pg_indexes 
-- WHERE tablename = 'chat_conversation' 
-- AND indexname LIKE 'idx_conversation%'
-- ORDER BY pg_relation_size(indexrelid) DESC;
