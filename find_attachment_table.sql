-- ============================================================================
-- DESCOBRIR NOME DA TABELA DE ANEXOS
-- ============================================================================

-- 1. Listar todas as tabelas que contenham "attachment" no nome
SELECT 
    table_schema,
    table_name
FROM information_schema.tables 
WHERE table_name LIKE '%attachment%'
ORDER BY table_name;

-- 2. Listar todas as tabelas do app "chat"
SELECT 
    table_schema,
    table_name
FROM information_schema.tables 
WHERE table_name LIKE 'chat_%'
ORDER BY table_name;

-- 3. Listar TODAS as tabelas (para ver estrutura)
SELECT 
    table_schema,
    table_name
FROM information_schema.tables 
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_name;













