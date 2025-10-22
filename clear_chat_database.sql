-- ============================================================================
-- SCRIPT SQL PARA LIMPAR TODOS OS DADOS DO CHAT
-- ============================================================================
-- ATENÇÃO: Este script é IRREVERSÍVEL!
-- Execute apenas se tiver certeza que quer deletar TUDO do chat.
-- 
-- REQUISITO: Desconectar instâncias WhatsApp ANTES de executar
-- ============================================================================

-- 1. Ver estatísticas ANTES de deletar
SELECT 'ANTES DA LIMPEZA' as status;

SELECT 
    'Anexos' as tabela,
    COUNT(*) as total
FROM chat_attachment
UNION ALL
SELECT 
    'Mensagens' as tabela,
    COUNT(*) as total
FROM chat_message
UNION ALL
SELECT 
    'Conversas' as tabela,
    COUNT(*) as total
FROM chat_conversation
UNION ALL
SELECT 
    'Participants (M2M)' as tabela,
    COUNT(*) as total
FROM chat_conversation_participants;

-- ============================================================================
-- 2. LIMPEZA (descomente as linhas abaixo para executar)
-- ============================================================================

-- ATENÇÃO: Remova os comentários (--) das linhas abaixo para executar!
-- Isso é uma proteção para evitar execução acidental.

-- Deletar anexos (primeiro porque tem FK para mensagens)
-- DELETE FROM chat_attachment;

-- Deletar mensagens (tem FK para conversas)
-- DELETE FROM chat_message;

-- Deletar relação many-to-many de participantes
-- DELETE FROM chat_conversation_participants;

-- Deletar conversas
-- DELETE FROM chat_conversation;

-- ============================================================================
-- 3. Verificar depois da limpeza
-- ============================================================================

SELECT 'DEPOIS DA LIMPEZA' as status;

SELECT 
    'Anexos' as tabela,
    COUNT(*) as total
FROM chat_attachment
UNION ALL
SELECT 
    'Mensagens' as tabela,
    COUNT(*) as total
FROM chat_message
UNION ALL
SELECT 
    'Conversas' as tabela,
    COUNT(*) as total
FROM chat_conversation
UNION ALL
SELECT 
    'Participants (M2M)' as tabela,
    COUNT(*) as total
FROM chat_conversation_participants;

-- ============================================================================
-- 4. Resetar sequences (IDs auto-incrementais) - OPCIONAL
-- ============================================================================
-- Apenas se você quiser que os IDs recomecem do 1
-- Não é necessário para UUIDs, mas útil para IDs numéricos

-- ALTER SEQUENCE chat_message_id_seq RESTART WITH 1;
-- ALTER SEQUENCE chat_messageattachment_id_seq RESTART WITH 1;

-- ============================================================================
-- NOTAS IMPORTANTES:
-- ============================================================================
-- 
-- 1. Este script NÃO deleta:
--    - Usuários (authn_user)
--    - Departamentos (authn_department)
--    - Tenants (tenancy_tenant)
--    - Instâncias WhatsApp (connections_evolutionconnection)
--    
-- 2. Apenas deleta dados do módulo CHAT:
--    - Conversas (chat_conversation)
--    - Mensagens (chat_message)
--    - Anexos (chat_attachment)
--    - Relação de participantes (chat_conversation_participants)
--
-- 3. Ordem de deleção respeitada (FK constraints):
--    Anexos → Mensagens → Participants → Conversas
--
-- 4. Backup recomendado ANTES de executar:
--    pg_dump -U postgres -d nome_do_banco > backup_chat_$(date +%Y%m%d).sql
--
-- ============================================================================

