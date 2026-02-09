-- ==========================================
-- VERIFICAÇÃO DE ÍNDICES EXISTENTES
-- Sistema de Conversas Privadas por Usuário
-- 
-- Execute este script ANTES de aplicar novos índices para verificar o que já existe
-- ==========================================

-- Listar todos os índices da tabela chat_conversation
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'chat_conversation'
ORDER BY indexname;

-- Verificar tamanho dos índices (útil para identificar índices grandes)
SELECT 
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    pg_relation_size(indexrelid) AS index_size_bytes
FROM pg_indexes 
WHERE tablename = 'chat_conversation'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Verificar estatísticas de uso dos índices (PostgreSQL 9.2+)
-- Útil para identificar índices não utilizados
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan AS index_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes 
WHERE tablename = 'chat_conversation'
ORDER BY idx_scan DESC;

-- Verificar índices específicos relacionados a assigned_to e department
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'chat_conversation'
AND (
    indexdef LIKE '%assigned_to%' 
    OR indexdef LIKE '%department%'
    OR indexdef LIKE '%status%'
)
ORDER BY indexname;
