-- ============================================================
-- SCRIPT SQL PARA LIMPAR CONVERSAS DE UM TENANT ESPECÍFICO
-- ============================================================
-- ⚠️  ATENÇÃO: Substitua 'TENANT_ID_AQUI' pelo UUID do tenant
-- ============================================================

-- Substituir pelo ID do tenant (UUID)
-- Exemplo: '123e4567-e89b-12d3-a456-426614174000'
\set tenant_id 'TENANT_ID_AQUI'

-- Verificar quantos registros serão deletados ANTES de deletar
SELECT 
    'Anexos' as tipo,
    COUNT(*) as quantidade
FROM chat_messageattachment ma
INNER JOIN chat_message m ON ma.message_id = m.id
INNER JOIN chat_conversation c ON m.conversation_id = c.id
WHERE c.tenant_id = :'tenant_id'
UNION ALL
SELECT 
    'Mensagens' as tipo,
    COUNT(*) as quantidade
FROM chat_message m
INNER JOIN chat_conversation c ON m.conversation_id = c.id
WHERE c.tenant_id = :'tenant_id'
UNION ALL
SELECT 
    'Conversas' as tipo,
    COUNT(*) as quantidade
FROM chat_conversation
WHERE tenant_id = :'tenant_id';

-- 1️⃣ Deletar anexos do tenant
DELETE FROM chat_messageattachment
WHERE message_id IN (
    SELECT m.id
    FROM chat_message m
    INNER JOIN chat_conversation c ON m.conversation_id = c.id
    WHERE c.tenant_id = :'tenant_id'
);

-- 2️⃣ Deletar mensagens do tenant
DELETE FROM chat_message
WHERE conversation_id IN (
    SELECT id
    FROM chat_conversation
    WHERE tenant_id = :'tenant_id'
);

-- 3️⃣ Deletar conversas do tenant
DELETE FROM chat_conversation
WHERE tenant_id = :'tenant_id';

-- Verificar se foi deletado
SELECT 
    'Conversas restantes do tenant' as tipo,
    COUNT(*) as quantidade
FROM chat_conversation
WHERE tenant_id = :'tenant_id';

